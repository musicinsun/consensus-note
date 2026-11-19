"""노션 '컨센서스 프로젝트' DB를 읽어 data.js를 새로 만들고, 본문 이미지는 연도별 이미지 저장소에 올립니다.

사용법:  NOTION_TOKEN=... IMAGES_TOKEN=... python sync_notion.py
필요: 노션 내부 통합(Integration) 토큰, 그리고 DB 페이지에서 그 통합을 '연결'해 두기.
     IMAGES_TOKEN: consensus-images-<연도> 저장소에 쓸 수 있는 GitHub 토큰 (없으면 이미지는 건너뜀)

- 모든 리포트의 노션 본문을 블로그용 HTML로 변환해 data.js의 window.NOTES에 저장
- 본문 이미지는 리포트 날짜의 연도별 저장소(musicinsun/consensus-images-<연도>)에 올림
  (노션 이미지 주소는 1시간이면 만료되고, 네이버 블로그가 이 주소를 직접 불러오므로 지우면 안 됨)
- 지난 동기화 이후 수정된 페이지만 다시 읽음 (last_edited_time 비교)
- Pillow가 있으면 이미지를 가로 1200px, JPEG로 줄여 저장
"""
import datetime
import html
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

try:
    from PIL import Image
except ImportError:  # 없으면 원본 그대로 저장
    Image = None

DATA_SOURCE_ID = "3f74d3d8-697c-8006-b6b3-000b3e6d9a6b"
OP_CODES = {"CONVICTION BUY": "C", "BUY": "B", "HOLD": "H", "SELL": "S", "NR": "N", "수주 코멘트": "J"}
ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "data.js"
IMG_OWNER = "musicinsun"
IMG_REPO = "consensus-images-{year}"
IMG_URL = "https://musicinsun.github.io/consensus-images-{year}/"
IMG_WORK = ROOT / ".imgrepos"
HEADERS = {}


# ── 노션 API 호출 (초당 3회 제한 → 간격 두고, 429면 기다렸다 재시도) ──
def api(url, body=None):
    for attempt in range(6):
        time.sleep(0.34)
        req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, HEADERS,
                                     method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
                continue
            raise


def query_all():
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    cursor, pages = None, []
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = api(url, body)
        pages += res["results"]
        if not res.get("has_more"):
            return pages
        cursor = res["next_cursor"]


def children(block_id):
    out, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        res = api(url)
        out += res["results"]
        if not res.get("has_more"):
            return out
        cursor = res["next_cursor"]


# ── 이미지 저장: 연도별 GitHub 저장소 ──
def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


class ImageStore:
    """연도별 이미지 저장소를 파일 내용 없이(목록만) 받아 두고, 새 이미지만 추가해 마지막에 한 번에 올림."""

    def __init__(self):
        self.token = os.environ.get("IMAGES_TOKEN", "")
        self.repos = {}  # year -> (dir, 기존 파일 이름 set) 또는 None(사용 불가)
        self.added = {}  # year -> [파일 이름]

    def repo(self, year):
        if year in self.repos:
            return self.repos[year]
        if not self.token:
            self.repos[year] = None
            return None
        d = IMG_WORK / str(year)
        url = f"https://x-access-token:{self.token}@github.com/{IMG_OWNER}/{IMG_REPO.format(year=year)}.git"
        try:
            if not d.exists():
                IMG_WORK.mkdir(exist_ok=True)
                subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout", url, str(d)],
                               check=True, capture_output=True, text=True)
                git(d, "read-tree", "HEAD")
            names = set(git(d, "ls-tree", "-r", "--name-only", "HEAD").split())
            self.repos[year] = (d, names)
        except subprocess.CalledProcessError as e:
            print(f"이미지 저장소 {IMG_REPO.format(year=year)} 를 열 수 없어요: {e.stderr.strip()[:200]}")
            self.repos[year] = None
        return self.repos[year]

    def save(self, year, block_id, url):
        """이미지 공개 주소를 돌려줌. 이미 올라가 있으면 다시 받지 않음."""
        r = self.repo(year)
        if r is None:
            return None
        d, names = r
        for ext in (".jpg", ".png", ".gif", ".webp"):
            if block_id + ext in names:
                return IMG_URL.format(year=year) + block_id + ext
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        name = compress(raw, d, block_id)
        names.add(name)
        self.added.setdefault(year, []).append(name)
        return IMG_URL.format(year=year) + name

    def push(self):
        for year, files in self.added.items():
            d = self.repos[year][0]
            git(d, "config", "user.name", "notion-sync")
            git(d, "config", "user.email", "notion-sync@users.noreply.github.com")
            git(d, "add", "--", *files)
            git(d, "commit", "-q", "-m", f"이미지 {len(files)}개 추가")
            git(d, "push", "-q", "origin", "HEAD:main")
            print(f"{IMG_REPO.format(year=year)} 에 이미지 {len(files)}개 올림")


def compress(raw, d, block_id):
    """가로 1200px JPEG로 줄여 저장하고 파일 이름을 돌려줌 (Pillow 없거나 움짤이면 원본)."""
    try:
        if Image is None:
            raise RuntimeError
        import io
        with Image.open(io.BytesIO(raw)) as im:
            if getattr(im, "is_animated", False):
                raise RuntimeError
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, "white")
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            if im.width > 1200:
                im = im.resize((1200, round(im.height * 1200 / im.width)))
            im.save(d / (block_id + ".jpg"), "JPEG", quality=75, optimize=True)
        return block_id + ".jpg"
    except Exception:
        ext = ".gif" if raw[:3] == b"GIF" else ".png" if raw[:4] == b"\x89PNG" else ".webp" if raw[8:12] == b"WEBP" else ".jpg"
        (d / (block_id + ext)).write_bytes(raw)
        return block_id + ext


STORE = ImageStore()
PAGE_YEAR = [datetime.date.today().year]  # 지금 변환 중인 리포트의 연도
IMG_FAILED = [False]  # 이번 페이지에서 이미지 저장에 실패했는지 (실패하면 다음에 다시 읽음)


# ── 노션 페이지 본문 → 블로그에 붙여넣기 좋은 HTML ──
COLORS = {"gray": "#787774", "brown": "#9f6b53", "orange": "#d9730d", "yellow": "#cb912f", "green": "#448361",
          "blue": "#337ea9", "purple": "#9065b0", "pink": "#c14c8a", "red": "#d44c47"}
BG = {"gray": "#f1f1ef", "brown": "#f4eeee", "orange": "#fbecdd", "yellow": "#fbf3db", "green": "#edf3ec",
      "blue": "#e7f3f8", "purple": "#f6f3f9", "pink": "#faf1f5", "red": "#fdebec"}


def rich(items):
    parts = []
    for it in items or []:
        t = html.escape(it.get("plain_text", "")).replace("\n", "<br>")
        a = it.get("annotations", {})
        if a.get("code"):
            t = f"<code>{t}</code>"
        if a.get("bold"):
            t = f"<b>{t}</b>"
        if a.get("italic"):
            t = f"<i>{t}</i>"
        if a.get("underline"):
            t = f"<u>{t}</u>"
        if a.get("strikethrough"):
            t = f"<s>{t}</s>"
        color = a.get("color", "default")
        if color.endswith("_background") and color[:-11] in BG:
            t = f'<span style="background-color:{BG[color[:-11]]}">{t}</span>'
        elif color in COLORS:
            t = f'<span style="color:{COLORS[color]}">{t}</span>'
        href = it.get("href") or ""
        if href.startswith("http"):
            t = f'<a href="{html.escape(href)}">{t}</a>'
        parts.append(t)
    return "".join(parts)


def image_html(b, v):
    src = (v.get("file") or {}).get("url") or (v.get("external") or {}).get("url")
    cap = rich(v.get("caption"))
    if not src:
        return ""
    try:
        path = STORE.save(PAGE_YEAR[0], b["id"].replace("-", ""), src)
    except Exception as e:
        print(f"  이미지 저장 실패 {b['id']}: {e}")
        path = None
    if not path:
        IMG_FAILED[0] = True
        return '<p style="color:#999">[이미지: 노션에서 확인]</p>'
    out = f'<p><img src="{path}" style="max-width:100%"></p>'
    return out + (f'<p style="color:#888;font-size:13px">{cap}</p>' if cap else "")


def blocks_html(block_id, depth=0):
    out, lst = [], None
    for b in children(block_id):
        t = b["type"]
        v = b.get(t, {})
        kids = blocks_html(b["id"], depth + 1) if b.get("has_children") and depth < 3 and t not in ("child_page", "child_database", "table") else ""
        tag = {"bulleted_list_item": "ul", "numbered_list_item": "ol"}.get(t)
        if tag != lst:
            if lst:
                out.append(f"</{lst}>")
            if tag:
                out.append(f"<{tag}>")
            lst = tag
        txt = rich(v.get("rich_text"))
        if tag:
            out.append(f"<li>{txt}{kids}</li>")
        elif t == "paragraph":
            out.append(f"<p>{txt or '&nbsp;'}</p>{kids}")
        elif t in ("heading_1", "heading_2", "heading_3"):
            n = {"heading_1": 2, "heading_2": 3, "heading_3": 4}[t]
            out.append(f"<h{n}>{txt}</h{n}>{kids}")
        elif t == "to_do":
            out.append(f"<p>{'☑' if v.get('checked') else '☐'} {txt}</p>{kids}")
        elif t == "quote":
            out.append(f'<blockquote style="border-left:3px solid #999;margin:8px 0;padding:2px 0 2px 12px;color:#555">{txt}{kids}</blockquote>')
        elif t == "callout":
            icon = (v.get("icon") or {}).get("emoji", "💡")
            out.append(f'<p style="background-color:#f1f1ef;padding:10px 12px">{icon} {txt}</p>{kids}')
        elif t == "toggle":
            out.append(f"<p><b>{txt}</b></p>{kids}")
        elif t == "divider":
            out.append("<hr>")
        elif t == "code":
            out.append(f"<pre>{txt}</pre>")
        elif t == "table":
            head = v.get("has_column_header")
            cells = []
            for i, r in enumerate(children(b["id"])):
                c = "th" if head and i == 0 else "td"
                cells.append("<tr>" + "".join(
                    f'<{c} style="border:1px solid #ccc;padding:4px 8px">{rich(x)}</{c}>' for x in r["table_row"]["cells"]) + "</tr>")
            out.append('<table style="border-collapse:collapse">' + "".join(cells) + "</table>")
        elif t == "image":
            out.append(image_html(b, v))
        elif t in ("file", "pdf", "video"):
            out.append('<p style="color:#999">[첨부: 노션에서 확인]</p>')
        elif t in ("bookmark", "embed", "link_preview"):
            u = html.escape(v.get("url", ""))
            out.append(f'<p><a href="{u}">{u}</a></p>')
        elif t in ("column_list", "column", "synced_block"):
            out.append(kids)
        elif txt:
            out.append(f"<p>{txt}</p>{kids}")
    if lst:
        out.append(f"</{lst}>")
    return "".join(out)


# ── DB 속성 ──
def text(prop):
    if not prop:
        return None
    items = prop.get("rich_text") or prop.get("title") or []
    s = "".join(i.get("plain_text", "") for i in items).strip()
    return s or None


def row(page):
    p = page["properties"]
    date = (p.get("날짜별 묶음") or {}).get("select")
    study = (p.get("추가 공부") or {}).get("select")
    pick = ((p.get("선정") or {}).get("select") or {}).get("name")
    ops = [OP_CODES.get(o["name"], o["name"]) for o in (p.get("투자 의견") or {}).get("multi_select", [])]
    return [
        page["id"].replace("-", ""),
        date["name"] if date else None,
        text(p.get("기업명")),
        text(p.get("증권사")),
        "|".join(ops) or None,
        (p.get("UPSIDE") or {}).get("number"),
        None if not study else (1 if study["name"] == "공부하자" else 0),
        {"오늘의": 1, "금주의": 2}.get(pick),  # 선정: 1=오늘의, 2=금주의
        text(p.get("선정 이유")),
    ]


def previous_notes():
    """지난번 data.js의 본문을 읽어 와서, 수정되지 않은 페이지는 다시 읽지 않게 함."""
    if not OUT.exists():
        return {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        if line.startswith("window.NOTES = "):
            try:
                old = json.loads(line[len("window.NOTES = "):].rstrip(";"))
            except ValueError:
                return {}
            return {k: v for k, v in old.items() if isinstance(v, dict)}
    return {}


def main():
    token = os.environ["NOTION_TOKEN"]
    HEADERS.update({"Authorization": f"Bearer {token}", "Notion-Version": "2025-09-03", "Content-Type": "application/json"})
    pages = [pg for pg in query_all() if not pg.get("in_trash") and not pg.get("archived")]
    pages.sort(key=lambda pg: pg["created_time"], reverse=True)
    rows = [row(pg) for pg in pages]
    rows.sort(key=lambda r: r[1] or "", reverse=True)  # 날짜 내림차순 (같은 날은 최근 생성 순)

    # ONLY_DATES="261117,261118" 처럼 주면 그 날짜 리포트의 본문만 새로 읽음 (나머지는 지난번 것 유지)
    only = {d.strip() for d in os.environ.get("ONLY_DATES", "").split(",") if d.strip()}
    date_of = {r[0]: r[1] for r in rows}
    old, notes, fetched = previous_notes(), {}, 0
    for pg in pages:
        pid, edited = pg["id"].replace("-", ""), pg["last_edited_time"]
        if pid in old and old[pid].get("t") == edited:
            notes[pid] = old[pid]
            continue
        if only and date_of.get(pid) not in only:
            if pid in old:
                notes[pid] = old[pid]
            continue
        d = date_of.get(pid)
        PAGE_YEAR[0] = 2000 + int(d[:2]) if d and d[:2].isdigit() else datetime.date.today().year
        IMG_FAILED[0] = False
        try:
            h = blocks_html(pid)
            notes[pid] = {"t": "" if IMG_FAILED[0] else edited, "h": h}  # 이미지 실패 시 다음 동기화에서 다시 시도
            fetched += 1
        except Exception as e:  # 한 페이지 실패가 전체 동기화를 막지 않게
            print(f"본문 읽기 실패 {pid}: {e}")
            if pid in old:
                notes[pid] = old[pid]

    STORE.push()
    # 예전 형식(사이트 안 images/ 폴더) 경로를 연도별 저장소 주소로 바꿈
    for pid, n in notes.items():
        if 'src="images/' in n.get("h", ""):
            d = date_of.get(pid)
            y = 2000 + int(d[:2]) if d and d[:2].isdigit() else datetime.date.today().year
            n["h"] = n["h"].replace('src="images/', f'src="{IMG_URL.format(year=y)}')

    lines = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    notes_js = json.dumps(notes, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    today = datetime.date.today().isoformat()
    OUT.write_text(
        "// 노션 '컨센서스 프로젝트' 데이터 스냅샷. sync_notion.py가 자동 생성합니다.\n"
        "// 행: [ID, 날짜, 기업명, 증권사, 투자의견, UPSIDE, 추가공부, 선정(1=오늘의 2=금주의), 선정 이유]\n"
        f'window.CONSENSUS = {{\nupdated: "{today}",\nrows: [\n{lines}\n]\n}};\n'
        "// 리포트별 노션 본문 {페이지ID: {t: 수정시각, h: HTML}}\n"
        f"window.NOTES = {notes_js};\n",
        encoding="utf-8",
    )
    added = sum(len(v) for v in STORE.added.values())
    print(f"{len(rows)}건 저장, 본문 {len(notes)}건 (이번에 새로 읽음 {fetched}건), 새 이미지 {added}개 → {OUT.name}")


if __name__ == "__main__":
    main()
