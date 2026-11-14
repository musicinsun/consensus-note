"""노션 '컨센서스 프로젝트' DB를 읽어 data.js를 새로 만듭니다.

사용법:  NOTION_TOKEN=secret_xxx python sync_notion.py
필요: 노션 내부 통합(Integration) 토큰, 그리고 DB 페이지에서 그 통합을 '연결'해 두기.
표준 라이브러리만 사용합니다.
"""
import datetime
import json
import os
import pathlib
import urllib.request

DATA_SOURCE_ID = "3f74d3d8-697c-8006-b6b3-000b3e6d9a6b"
OP_CODES = {"CONVICTION BUY": "C", "BUY": "B", "HOLD": "H", "SELL": "S", "NR": "N", "수주 코멘트": "J"}
OUT = pathlib.Path(__file__).with_name("data.js")


def query_all(token):
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }
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
    ops = [OP_CODES.get(o["name"], o["name"]) for o in (p.get("투자 의견") or {}).get("multi_select", [])]
    return [
        page["id"].replace("-", ""),
        date["name"] if date else None,
        text(p.get("기업명")),
        text(p.get("증권사")),
        "|".join(ops) or None,
        (p.get("UPSIDE") or {}).get("number"),
        None if not study else (1 if study["name"] == "공부하자" else 0),
    ]


def main():
    token = os.environ["NOTION_TOKEN"]
    pages = [pg for pg in query_all(token) if not pg.get("in_trash") and not pg.get("archived")]
    pages.sort(key=lambda pg: pg["created_time"], reverse=True)
    rows = [row(pg) for pg in pages]
    rows.sort(key=lambda r: r[1] or "", reverse=True)  # 날짜 내림차순 (같은 날은 최근 생성 순)
    lines = ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    today = datetime.date.today().isoformat()
    OUT.write_text(
        "// 노션 '컨센서스 프로젝트' 데이터 스냅샷. sync_notion.py가 자동 생성합니다.\n"
        f'window.CONSENSUS = {{\nupdated: "{today}",\nrows: [\n{lines}\n]\n}};\n',
        encoding="utf-8",
    )
    print(f"{len(rows)}건 저장 → {OUT.name}")


if __name__ == "__main__":
    main()
