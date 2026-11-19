"""노션 '컨센서스 프로젝트' DB를 읽어 data.js를 새로 만듭니다.

사용법:  NOTION_TOKEN=secret_xxx python sync_notion.py
필요: 노션 내부 통합(Integration) 토큰, 그리고 DB 페이지에서 그 통합을 '연결'해 두기.
표준 라이브러리만 사용합니다.
"""
import datetime
import html
import json
import os
import pathlib
import urllib.request

DATA_SOURCE_ID = "3f74d3d8-697c-8006-b6b3-000b3e6d9a6b"
OP_CODES = {"CONVICTION BUY": "C", "BUY": "B", "HOLD": "H", "SELL": "S", "NR": "N", "수주 코멘트": "J"}
OUT = pathlib.Path(__file__).with_name("data.js")
HEADERS = {}


def query_all(token):
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    headers = HEADERS
    cursor, pages = None, []
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
        with urllib.request.urlopen(req) as r:
            res = json.load(r)
        pages += res["results"]
        if not res.get("has_more"):
            return pages
        cursor = res["next_cursor"]


# ── 노션 페이지 본문 → 블로그에 붙여넣기 좋은 HTML ──
COLORS = {"gray": "#787774", "brown": "#9f6b53", "orange": "#d9730d", "yellow": "#cb912f", "green": "#448361",
          "blue": "#337ea9", "purple": "#9065b0", "pink": "#c14c8a", "red": "#d44c47"}
BG = {"gray": "#f1f1ef", "brown": "#f4eeee", "orange": "#fbecdd", "yellow": "#fbf3db", "green": "#edf3ec",
      "blue": "#e7f3f8", "purple": "#f6f3f9", "pink": "#faf1f5", "red": "#fdebec"}


def children(block_id):
    out, cursor = [], None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS)) as r:
            res = json.load(r)
        out += res["results"]
        if not res.get("has_more"):
            return out
        cursor = res["next_cursor"]


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
        href = (it.get("href") or "")
        if href.startswith("http"):
            t = f'<a href="{html.escape(href)}">{t}</a>'
        parts.append(t)
    return "".join(parts)


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
            rows = children(b["id"])
            head = v.get("has_column_header")
            cells = []
            for i, r in enumerate(rows):
                c = "th" if head and i == 0 else "td"
                cells.append("<tr>" + "".join(
                    f'<{c} style="border:1px solid #ccc;padding:4px 8px">{rich(x)}</{c}>' for x in r["table_row"]["cells"]) + "</tr>")
            out.append('<table style="border-collapse:collapse">' + "".join(cells) + "</table>")
        elif t in ("image", "file", "pdf", "video"):
            cap = rich(v.get("caption"))
            out.append(f'<p style="color:#999">[{"이미지" if t == "image" else "첨부"}: 노션에서 확인{" · " + cap if cap else ""}]</p>')
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


def main():
    token = os.environ["NOTION_TOKEN"]
    HEADERS.update({"Authorization": f"Bearer {token}", "Notion-Version": "2025-09-03", "Content-Type": "application/json"})
    pages = [pg for pg in query_all(token) if not pg.get("in_trash") and not pg.get("archived")]
    pages.sort(key=lambda pg: pg["created_time"], reverse=True)
    rows = [row(pg) for pg in pages]
    rows.sort(key=lambda r: r[1] or "", reverse=True)  # 날짜 내림차순 (같은 날은 최근 생성 순)
    lines = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    today = datetime.date.today().isoformat()

    # 오늘의/금주의로 선정된 리포트만 노션 본문을 HTML로 가져옴 (블로그 글 초안용)
    notes = {}
    for r in rows:
        if r[7]:
            try:
                notes[r[0]] = blocks_html(r[0])
            except Exception as e:  # 한 페이지 실패가 전체 동기화를 막지 않게
                print(f"본문 읽기 실패 {r[2]}: {e}")
    notes_js = json.dumps(notes, ensure_ascii=False, indent=0).replace("</", "<\\/")

    OUT.write_text(
        "// 노션 '컨센서스 프로젝트' 데이터 스냅샷. sync_notion.py가 자동 생성합니다.\n"
        "// 행: [ID, 날짜, 기업명, 증권사, 투자의견, UPSIDE, 추가공부, 선정(1=오늘의 2=금주의), 선정 이유]\n"
        f'window.CONSENSUS = {{\nupdated: "{today}",\nrows: [\n{lines}\n]\n}};\n'
        "// 선정된 리포트의 노션 본문(HTML)\n"
        f"window.NOTES = {notes_js};\n",
        encoding="utf-8",
    )
    print(f"{len(rows)}건, 본문 {len(notes)}건 저장 → {OUT.name}")


if __name__ == "__main__":
    main()
