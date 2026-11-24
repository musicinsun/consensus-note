"""Update completed U.S. market sessions with licensed Barchart OnDemand data."""

import json
import math
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")
ARCHIVE = Path(__file__).with_name("us-market.js")
PREFIX = "window.US_MARKET = "
INDICES = {"SPX": "$SPX", "IXIC": "$NASX", "SOX": "$SOX", "RUT": "$RUT"}
BREADTH = {
    "NYSE": dict(up="$ADVN", down="$DECN", flat="$UNCN", high="$MAHN", low="$MALN"),
    "NASDAQ": dict(up="$ADVQ", down="$DECQ", flat="$UNCQ", high="$MAHQ", low="$MALQ"),
}


def request_rows(endpoint, key, **params):
    body = urlencode({"apikey": key, **params}).encode()
    request = Request(
        f"https://ondemand.websol.barchart.com/{endpoint}.json",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if attempt == 2 or exc.code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(f"Barchart {endpoint} HTTP {exc.code}") from None
        except (OSError, URLError, ValueError):
            if attempt == 2:
                raise RuntimeError(f"Barchart {endpoint} 응답을 읽을 수 없습니다.") from None
        else:
            code = payload.get("status", {}).get("code")
            if code != 200:
                raise RuntimeError(f"Barchart {endpoint} 요청 실패 (상태 {code})")
            return payload.get("results") or []
        time.sleep(2 ** attempt)


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    raise ValueError("누락되었거나 잘못된 수치")


def count(value):
    value = number(value)
    # Barchart special symbols can represent zero with 0.01.
    if value == 0.01:
        return 0
    if value < 0 or value != int(value):
        raise ValueError("종목 수가 정수가 아닙니다.")
    return int(value)


def parse_bars(rows, trade_date, previous, close_minute):
    points = {}
    for row in rows:
        if row.get("tradingDay") != trade_date or row.get("close") is None:
            continue
        timestamp = datetime.fromisoformat(row["timestamp"])
        if timestamp.tzinfo is None:
            raise ValueError("5분봉에서 시간대가 누락되었습니다.")
        local = timestamp.astimezone(NEW_YORK)
        minute = local.hour * 60 + local.minute
        price = number(row["close"])
        if local.date().isoformat() == trade_date and 570 <= minute <= close_minute and price > 0:
            points[minute] = round((price / previous - 1) * 100, 3)
    if not points or min(points) > 575 or max(points) < close_minute - 5:
        raise ValueError("정규장 시작 또는 마감 구간의 5분봉이 누락되었습니다.")
    return sorted(points.items())


def current_snapshot(key, sessions, now):
    symbols = [*INDICES.values(), *(symbol for group in BREADTH.values() for symbol in group.values())]
    quotes = {row["symbol"]: row for row in request_rows("getQuote", key, symbols=",".join(symbols))}
    trade_date = quotes.get("$SPX", {}).get("tradeDate")
    observed = date.fromisoformat(trade_date or "")
    if observed > now.date() or (observed == now.date() and now.hour < 17):
        raise ValueError("정규장 마감 이후에만 저장합니다.")
    if sessions and trade_date < max(sessions):
        raise ValueError("공급처 날짜가 최신 저장 기록보다 오래됐습니다.")
    if trade_date in sessions and not sessions[trade_date].get("seed"):
        return trade_date, None

    def close_quote(symbol):
        quote = quotes.get(symbol, {})
        if quote.get("tradeDate") != trade_date:
            raise ValueError(f"{symbol} 거래일이 {trade_date}와 일치하지 않습니다.")
        return quote

    breadth = {
        exchange: {metric: count(close_quote(symbol).get("lastPrice")) for metric, symbol in group.items()}
        for exchange, group in BREADTH.items()
    }
    if any(row["up"] + row["down"] + row["flat"] < 100 for row in breadth.values()):
        raise ValueError("거래소 등락 종목 집계가 충분하지 않습니다.")

    # The SPX quote's exchange timestamp identifies the regular or shortened close.
    quote_time = datetime.fromisoformat(close_quote("$SPX")["tradeTimestamp"])
    if quote_time.tzinfo is None:
        raise ValueError("마감 시세에서 시간대가 누락되었습니다.")
    closing_hour = quote_time.astimezone(NEW_YORK).hour
    close_minute = 780 if closing_hour == 13 else 960
    if closing_hour not in {13, 16}:
        raise ValueError("S&P 500 정규장 마감 시세를 확인할 수 없습니다.")

    indices, bars = {}, {}
    for name, symbol in INDICES.items():
        quote = close_quote(symbol)
        close = number(quote.get("lastPrice"))
        previous = close - number(quote.get("netChange"))
        if close <= 0 or previous <= 0:
            raise ValueError(f"{symbol} 지수 값이 잘못되었습니다.")
        indices[name] = {"close": close, "change": round((close / previous - 1) * 100, 2)}
        rows = request_rows(
            "getHistory", key, symbol=symbol, type="minutes", interval=5, order="asc",
            startDate=observed.strftime("%Y%m%d"), endDate=(observed + timedelta(days=1)).strftime("%Y%m%d"),
        )
        bars[name] = parse_bars(rows, trade_date, previous, close_minute)
    return trade_date, {"indices": indices, "breadth": breadth, "closeMinute": close_minute, "bars": bars}


def update(key):
    text = ARCHIVE.read_text(encoding="utf-8").strip()
    sessions = json.loads(text.removeprefix(PREFIX).removesuffix(";"))["sessions"]
    now = datetime.now(NEW_YORK)
    if now.weekday() < 5 and 9 <= now.hour < 17:
        print("미국장 마감 후에 실행해 주세요.")
        return
    trade_date, snapshot = current_snapshot(key, sessions, now)
    if snapshot is None:
        print(f"최신 저장 거래일 {trade_date}에 변경 사항이 없습니다.")
        return
    sessions[trade_date] = snapshot
    rows = [f"    {json.dumps(day)}: {json.dumps(value, separators=(',', ':'), allow_nan=False)}" for day, value in sorted(sessions.items())]
    result = PREFIX + '{\n  "sessions": {\n' + ',\n'.join(rows) + '\n  }\n};\n'
    pending = ARCHIVE.with_suffix(".tmp")
    pending.write_text(result, encoding="utf-8", newline="\n")
    pending.replace(ARCHIVE)
    print(f"미국장 {trade_date} 마감 기록 저장")


if __name__ == "__main__":
    api_key = os.environ.get("BARCHART_API_KEY", "").strip()
    if api_key:
        update(api_key)
    else:
        print("::warning::BARCHART_API_KEY가 설정되면 미국장 마감 기록을 갱신합니다.")
