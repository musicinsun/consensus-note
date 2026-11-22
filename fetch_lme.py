"""Westmetall에서 LME 알루미늄 현물가·3개월물·재고를 받아 lme.js를 새로 만듭니다.

사용법:  python fetch_lme.py
올해 포함 최근 3개년 표를 읽습니다 (6개월 전 가격 계산에 충분한 기간). 표준 라이브러리만 사용합니다.
"""
import datetime
import html
import json
import pathlib
import re
import urllib.request

URL = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Al_cash&year={year}"
YEARS_BACK = 2
OUT = pathlib.Path(__file__).with_name("lme.js")
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def num(s):
    s = s.replace(",", "").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def fetch_year(year):
    req = urllib.request.Request(URL.format(year=year), headers={"User-Agent": "Mozilla/5.0 (personal research dashboard)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    rows = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 4:
            continue
        m = re.match(r"(\d{1,2})\.\s*([A-Za-z]+)\s+(\d{4})", cells[0])
        if not m or m.group(2) not in MONTHS:
            continue
        d = datetime.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
        rows[d.isoformat()] = [d.isoformat(), num(cells[1]), num(cells[2]), num(cells[3])]
    return rows


STOCK_CODE = "006110"  # 삼아알미늄
STOCK_URL = "https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1&startTime={start}&endTime={end}&timeframe=day"


def fetch_stock(start_year):
    """네이버 금융 일봉(수정주가)에서 종가만 [날짜, 종가] 목록으로 돌려줌. 실패하면 빈 목록."""
    url = STOCK_URL.format(code=STOCK_CODE, start=f"{start_year}0101", end=datetime.date.today().strftime("%Y%m%d"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (personal research dashboard)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"주가를 받지 못했어요: {e}")
        return []
    out = []
    for d, close in re.findall(r'\["(\d{8})",\s*[\d.]+,\s*[\d.]+,\s*[\d.]+,\s*([\d.]+)', text):
        out.append([f"{d[:4]}-{d[4:6]}-{d[6:]}", int(float(close))])
    return out


def main():
    this_year = datetime.date.today().year
    rows = {}
    for y in range(this_year - YEARS_BACK, this_year + 1):
        rows.update(fetch_year(y))
    data = sorted(rows.values())
    if len(data) < 100:
        raise SystemExit(f"데이터가 너무 적어요 ({len(data)}건). 사이트 구조가 바뀌었는지 확인하세요.")
    stock = fetch_stock(this_year - YEARS_BACK)
    if not stock and OUT.exists():  # 주가만 실패했으면 지난번 주가를 유지
        m = re.search(r"^stock: (\[.*\])$", OUT.read_text(encoding="utf-8"), re.M)
        stock = json.loads(m.group(1)) if m else []
    lines = ",\n".join(json.dumps(r) for r in data)
    OUT.write_text(
        "// LME 알루미늄 (출처: westmetall.com) + 삼아알미늄 주가 (출처: 네이버 금융). fetch_lme.py가 자동 생성합니다.\n"
        "// rows: [날짜, 현물가(Cash-Settlement, USD/t), 3개월물(USD/t), 재고(t)]\n"
        "// stock: [날짜, 삼아알미늄(006110) 종가(원, 수정주가)]\n"
        f'window.LME = {{\nupdated: "{datetime.date.today().isoformat()}",\n'
        f"stock: {json.dumps(stock, separators=(',', ':'))}\n,\n"
        f"rows: [\n{lines}\n]\n}};\n",
        encoding="utf-8",
    )
    print(f"{len(data)}건 저장 ({data[0][0]} ~ {data[-1][0]}), 주가 {len(stock)}일 → {OUT.name}")


if __name__ == "__main__":
    main()
