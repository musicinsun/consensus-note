"""Calculate weekly snapshots of GPU and stock-return correlations."""

from bisect import bisect_right
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from math import isfinite
from statistics import StatisticsError, correlation
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


STOCKS = ("NVDA.US", "AVGO.US", "005930.KO", "000660.KO")
METRICS = ("p25", "low")
ONE_DAY = timedelta(days=1).total_seconds()


def monday(day):
    return day - timedelta(days=day.weekday())


def market_close(symbol, day):
    if symbol.endswith(".KO"):
        hour = 16 if day == date(2026, 11, 19) else 15  # CSAT session.
        return datetime.combine(day, time(hour, 30), ZoneInfo("Asia/Seoul"))

    after_thanksgiving = day.month == 11 and 23 <= day.day <= 29 and day.weekday() == 4
    holiday_eve = (day.month, day.day) in {(7, 3), (12, 24)}
    return datetime.combine(day, time(13 if after_thanksgiving or holiday_eve else 16),
                            ZoneInfo("America/New_York"))


def stock_sessions(symbol, rows, first, last):
    if not isinstance(rows, list):
        raise ValueError("Unexpected stock response")
    sessions = {}
    for row in rows:
        day = date.fromisoformat(row["date"])
        price = row["adjusted_close"]
        if first <= day <= last and type(price) in (int, float) and price > 0 and isfinite(price):
            sessions[day] = (day, market_close(symbol, day).timestamp(), price)
    return [sessions[day] for day in sorted(sessions)]


def returns_for(sessions, rentals, metric, weekly):
    if weekly:
        sessions = list({monday(session[0]): session for session in sessions}.values())
    quotes = sorted(
        (datetime.fromisoformat(row["at"]).timestamp(), row[metric])
        for row in rentals if row[metric] is not None
    )
    stamps = [stamp for stamp, _ in quotes]

    def match(close):
        i = bisect_right(stamps, close) - 1
        return i if i >= 0 and close - stamps[i] <= ONE_DAY else None

    for (previous_day, previous_close, previous_price), (day, close, price) in pairwise(sessions):
        if weekly and (monday(day) - monday(previous_day)).days != 7:
            continue
        previous_quote, quote = match(previous_close), match(close)
        if previous_quote is not None and quote is not None and previous_quote != quote:
            yield quotes[quote][1] / quotes[previous_quote][1] - 1, price / previous_price - 1


def measure(sessions, rentals, metric, weekly):
    samples = list(returns_for(sessions, rentals, metric, weekly))
    count = len(samples)
    if count < 3:
        return [None, count]
    try:
        return [round(correlation(*zip(*samples)), 5), count]
    except StatisticsError:
        return [None, count]


def build_report(gpu, stocks, first, last):
    report = {"from": first.isoformat(), "through": last.isoformat(), "source": "EODHD"}
    for label, weekly in (("daily", False), ("weekly", True)):
        report[label] = {
            metric: {
                model: [measure(sessions, rentals, metric, weekly) for sessions in stocks]
                for model, rentals in gpu.items()
            }
            for metric in METRICS
        }
    return report


def fetch_weekly_report(gpu, token, today, get_json):
    """Use a licensed EODHD key. Publish coefficients and counts, with no raw closes."""
    last_completed_week = monday(today) - timedelta(days=1)
    first = max(date.fromisoformat(rows[0]["date"]) for rows in gpu.values())
    stocks = []
    for symbol in STOCKS:
        query = urlencode({"api_token": token, "from": first, "to": last_completed_week,
                           "period": "d", "fmt": "json"})
        url = f"https://eodhd.com/api/eod/{symbol}?{query}"
        stocks.append(stock_sessions(symbol, get_json(url), first, last_completed_week))
    if any(not sessions or monday(sessions[-1][0]) != monday(last_completed_week) for sessions in stocks):
        raise ValueError("Missing or stale stock history")
    last = max(sessions[-1][0] for sessions in stocks)
    report = build_report(gpu, stocks, first, last)
    if not any(value is not None for row in report["daily"]["p25"].values() for value, _ in row):
        raise ValueError("No comparable returns")
    return report
