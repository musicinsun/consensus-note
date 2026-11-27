"""텔레그램 공시 정리 봇 (@Be_Known_News_bot)

사용법: 봇에게 공시 내용을 보내 두고, 정리하고 싶을 때 `/정리`를 보내면
그때까지 보낸 공시에서 핵심 항목을 뽑아 기업별 브리핑을 같은 대화창으로 보내 준다.

- GitHub Actions(.github/workflows/telegram-digest.yml)가 몇 분마다 이 스크립트를 실행한다.
- 공시의 항목명과 보고서명을 사용한다. 내용은 저장하지 않고, 로그에도 내용을 남기지 않는다.
- 텔레그램은 봇이 받은 메시지를 최대 24시간만 보관하므로, 보낸 지 24시간 안에 `/정리`를 해야 한다.
- 대화창(chat)별로 따로 정리한다. 다른 사람이 봇에게 보낸 메시지가 내 정리본에 섞이지 않는다.

필요: 환경변수 TELEGRAM_BOT_TOKEN
"""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from html import escape, unescape

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}/"
TRIGGERS = {"/정리", "정리", "/summary", "/digest"}
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = "월화수목금토일"

MAX_MSG = 3800  # HTML 태그와 페이지 번호를 포함해 여유를 둔다.

REPORT_TYPES = (
    ("지분 변동", ("대량보유상황", "대량보유", "지분변동")),
    ("공급계약", ("공급계약", "판매계약", "납품계약", "수주")),
    ("BW", ("신주인수권부사채", "BW")),
    ("CB", ("전환사채", "CB")),
    ("EB", ("교환사채", "EB")),
    ("유상증자", ("유상증자", "제3자배정")),
    ("자사주 소각", ("주식소각", "자사주소각", "자기주식소각")),
    ("자사주 처분", ("자기주식처분", "자사주처분")),
    ("자사주 취득", ("자기주식취득", "자사주취득")),
    ("실적", ("잠정실적", "영업실적", "연결재무제표기준", "손익구조", "실적")),
    ("배당", ("현금배당", "배당결정", "배당")),
)
FINANCING = ("CB", "BW", "EB")
FIELD = re.compile(r"^\s*(?:[•*▪·-]\s*)?([^:：\d][^:：]{0,39})\s*[:：]\s*(.+)$")
MONEY = re.compile(r"(\d+(?:\.\d+)?)(조|억|만|천)?")
WON_UNITS = {"조": 10**12, "억": 10**8, "만": 10**4, "천": 10**3, None: 1}


@dataclass
class Disclosure:
    company: str
    kind: str
    report: str
    details: str
    url: str
    amount: Decimal | None = None
    weight: Decimal | None = None
    terms: tuple[str, ...] = ()
    headline_detail: str = ""

    @property
    def corrected(self):
        return "정정" in self.report

    @property
    def headline(self):
        label = self.kind or self.report or "공시"
        if self.corrected and self.kind:
            label += " 정정"
        return label


def call(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(API + method, data), timeout=30) as r:
        res = json.load(r)
    if not res.get("ok"):
        raise RuntimeError(f"{method} 실패: {res.get('description')}")
    return res["result"]


def text_of(msg):
    return (msg.get("text") or msg.get("caption") or "").strip()


def compact(text, limit):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def label_key(label):
    return re.sub(r"\s+", "", label).casefold()


def report_kind(report):
    title = label_key(report)
    for kind, terms in REPORT_TYPES:
        if any(label_key(term) in title for term in terms if len(term) > 2):
            return kind
    for kind in FINANCING:
        if re.search(rf"(?<![a-z]){kind.lower()}(?![a-z])", title):
            return kind
    return ""


def parse_won(text):
    value = re.sub(r"[\s,]", "", text).removesuffix("원")
    if len(value) > 40:
        return None
    if not (text.strip().endswith("원") or re.search(r"[조억만천]$", value)):
        return None
    if not re.fullmatch(r"(?:\d+(?:\.\d+)?[조억만천]?)+", value):
        return None
    return sum(Decimal(number) * WON_UNITS[unit or None] for number, unit in MONEY.findall(value))


def number_text(value):
    integer, _, fraction = f"{value:,f}".partition(".")
    fraction = fraction.rstrip("0")
    return f"{integer}.{fraction}" if fraction else integer


def format_won(value):
    if value >= WON_UNITS["억"]:
        return number_text(value / WON_UNITS["억"]) + "억 원"
    return number_text(value) + "원"


def percent_value(text):
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%", text)
    return Decimal(match[1]) if match else None


def disclosure_fields(text):
    fields = {}
    lines = unescape(text).replace("\u200b", "").splitlines()
    for line in lines:
        if match := FIELD.match(line):
            key = label_key(match[1])
            item = match[2].strip()
            if item and item not in {"-", "–", "—"}:
                fields.setdefault(key, item)
    return fields, lines


def link_url(value):
    url = value.split()[0] if value else ""
    if len(url) <= 350 and re.fullmatch(r"https?://[^\s<>\"']+", url, re.IGNORECASE):
        return url
    return ""


def investor_summary(lines):
    for index, line in enumerate(lines):
        if line.strip().lstrip("*• ") not in {"투자자", "대상자", "배정대상자"}:
            continue
        names = []
        for entry in lines[index + 1:]:
            entry = entry.strip()
            if not entry or FIELD.match(entry):
                break
            names.append(entry)
            if len(names) == 2:
                break
        if names:
            return compact(names[0], 60) + (" 등" if len(names) > 1 else "")
    return ""


def parse_disclosure(text):
    fields, lines = disclosure_fields(text)

    def field(*labels):
        return next((fields[label_key(label)] for label in labels if label_key(label) in fields), "")

    def phrases(*labels_and_values):
        return [f"{label} {compact(value, 65)}" if label else compact(value, 65)
                for label, value in labels_and_values if value]

    def period(start, end):
        return "~".join(part for part in (start, end) if part)

    company = field("기업명", "회사명", "종목명", "법인명")
    company = re.split(r"\s*\(\s*시가총액\b", company, maxsplit=1)[0]
    company = compact(re.sub(r"\s+[A-Z]?\d{6}$", "", company), 55)
    report = compact(field("보고서명", "공시명", "공시 제목"), 115)
    content_lines = [line.strip() for line in lines if line.strip()
                     and not re.match(r"^\s*[•\s]*\d{4}[./-]", line)]
    kind = report_kind(report or (content_lines[0] if content_lines else ""))
    url = link_url(field("공시링크", "공시 링크", "DART 링크", "원문 링크"))
    amount_text = ""
    weight = None
    terms = []
    details = []
    headline_detail = ""

    if kind == "공급계약":
        amount_text = field("계약금액", "계약 금액", "계약금액(원)", "수주금액")
        ratio = field("매출대비", "매출액대비", "매출액 대비(%)", "최근매출액대비", "최근 매출액 대비(%)")
        if not ratio:
            match = re.search(r"매출(?:액)?\s*대비\s*[:：]\s*([\d.]+\s*%)", amount_text)
            if match:
                ratio = match[1]
        weight = percent_value(ratio) if ratio.endswith("%") else percent_value(ratio + "%")
        details = phrases(("매출 대비", f"{number_text(weight)}%" if weight is not None else ratio),
                          ("계약 상대", field("계약상대", "계약상대방")),
                          ("계약 기간", field("계약기간") or period(field("시작일", "계약시작일"), field("종료일", "계약종료일"))))
    elif kind in FINANCING or kind == "유상증자":
        amount_text = field("발행금액", "조달금액", "증자금액", "유상증자금액", "발행총액", "권면총액")
        price = field("전환가액", "행사가액", "교환가액", "발행가액", "발행가").partition("(")[0].strip()
        terms = [compact(value, 65) for value in (field("발행방법"), price, field("표면이율"),
                                                 field("만기이율"), field("납입일자", "납입일"))]
        details = phrases(("목적", field("조달목적", "자금조달목적", "자금조달의 목적", "발행목적")),
                          ("대상", field("대상자", "배정대상자", "인수인", "투자자") or investor_summary(lines)))
    elif kind.startswith("자사주"):
        amount_text = field("취득예정금액", "취득금액", "처분예정금액", "소각예정금액", "소각금액", "금액")
        details = phrases(("주식 수", field("취득예정주식", "처분예정주식", "소각예정주식", "주식수", "수량")),
                          ("기간", field("취득예정기간", "처분예정기간", "기간") or period(field("시작일"), field("종료일"))),
                          ("예정일", field("소각예정일", "소각일")))
    elif kind == "실적":
        details = phrases(("매출", field("매출액", "매출")), ("영업이익", field("영업이익")),
                          ("순이익", field("당기순이익", "순이익")), ("전년 대비", field("YoY", "전년동기대비")),
                          ("전분기 대비", field("QoQ", "전분기대비")))
    elif kind == "지분 변동":
        before, after = field("보고전", "변동전", "변동전비율"), field("보고후", "변동후", "변동후비율")
        holder = field("대표보고", "대표보고자", "보고자").partition("/")[0].strip()
        movement = f"{before} → {after}" if before and after else after
        change = ""
        previous, current = percent_value(before), percent_value(after)
        if previous is not None and current is not None:
            weight = abs(current - previous)
            change = ("+" if current > previous else "") + number_text(current - previous) + "%p"
            headline_detail = " ".join(part for part in (compact(holder, 55), "보유비율", movement) if part)
        reason = field("보고사유")
        details = phrases(("변동폭", change), ("", reason), ("보유 목적", field("보유목적") if not reason else ""))
        if not headline_detail:
            details = phrases(("", holder), ("보유비율", movement)) + details
    elif kind == "배당":
        details = phrases(("주당", field("주당배당금", "1주당배당금", "보통주배당금")),
                          ("배당수익률", field("시가배당률", "배당수익률")),
                          ("기준일", field("배당기준일")), ("지급 예정일", field("배당금지급예정일")))

    amount_text = amount_text.partition("(")[0].strip()
    amount = parse_won(amount_text) if amount_text else None
    if amount_text:
        details.insert(0, format_won(amount) if amount is not None else compact(amount_text, 65))
    if not details and not report and not any(terms):
        excerpt = next((line for line in content_lines if not FIELD.match(line) and not link_url(line)), "")
        details = phrases(("", excerpt))
    return Disclosure(company, kind, report, " · ".join(details), url, amount, weight, tuple(terms), headline_detail)


def combined_amount(group):
    kinds = {report.kind for report in group}
    urls = {report.url for report in group if report.url}
    if (len(group) > 1 and len(urls) == len(group)
            and (kinds <= set(FINANCING) or kinds == {"공급계약"})
            and all(report.amount is not None and not report.corrected for report in group)):
        return sum(report.amount for report in group)
    return None


def ranking(group):
    total = combined_amount(group)
    amount = total if total is not None else max((report.amount or 0 for report in group), default=0)
    weight = max((report.weight or 0 for report in group), default=0)
    return amount, weight


def source_line(report):
    return f'<a href="{escape(report.url, quote=True)}">{escape(report.headline)} 원문</a>' if report.url else ""


def financing_terms(terms, price_label):
    method, price, coupon, maturity, payment = terms
    parts = [method, f"{price_label} {price}" if price else ""]
    if coupon and coupon == maturity:
        parts.append(f"표면·만기이율 {coupon}")
    else:
        if coupon:
            parts.append(f"표면이율 {coupon}")
        if maturity:
            parts.append(f"만기이율 {maturity}")
    if payment:
        parts.append(f"납입 예정일 {payment}")
    return " · ".join(part for part in parts if part)


def company_lines(group):
    first = group[0]
    name = first.company
    sources = [source_line(report) for report in group if report.url]
    total = combined_amount(group)
    shared_terms = ""
    if total is not None:
        if first.kind == "공급계약":
            headline = f"공급계약 {len(group)}건 · 총 {format_won(total)}"
        else:
            present = {report.kind for report in group}
            kinds = "·".join(kind for kind in FINANCING if kind in present)
            headline = f"{kinds}로 총 {format_won(total)} 조달 결정"
            if first.terms and all(report.terms == first.terms for report in group):
                labels = {"CB": "전환가", "BW": "행사가", "EB": "교환가"}
                price_label = "·".join(labels[kind] for kind in FINANCING if kind in present)
                shared_terms = financing_terms(first.terms, price_label)
    elif len(group) > 1:
        headline = f"공시 {len(group)}건"
    elif first.amount is not None:
        headline = f"{first.headline} · {format_won(first.amount)}"
    else:
        headline = first.headline_detail or first.headline
        if first.corrected and first.headline_detail:
            headline += " (정정)"

    lines = [f"<b>{escape(f'{name} | {headline}' if name else headline)}</b>"]
    for report in group:
        detail = report.details
        if len(group) == 1 and report.amount is not None:
            detail = detail.removeprefix(format_won(report.amount)).removeprefix(" · ")
        if report.terms and not shared_terms:
            label = {"CB": "전환가", "BW": "행사가", "EB": "교환가"}.get(report.kind, "발행가")
            terms = financing_terms(report.terms, label)
            detail = " · ".join(part for part in (detail, terms) if part)
        if not detail and report.report and report.headline != report.report:
            detail = report.report
        if len(group) > 1:
            detail = f"{report.headline} · {detail}" if detail else report.headline
        if detail:
            lines.append(escape(compact(detail, 460)))
    if shared_terms:
        lines.append(escape(shared_terms))
    for start in range(0, len(sources), 2):
        pair = sources[start:start + 2]
        joined = " · ".join(pair)
        lines.extend([joined] if message_length(joined) < MAX_MSG else pair)
    return lines


def message_length(text):
    return len(text.encode("utf-16-le")) // 2


def pack_messages(head, sections):
    messages = []
    current = head
    for blocks in sections:
        for block in blocks:
            joined = "\n".join(block)
            if message_length(joined) + 2 <= MAX_MSG:
                if message_length(current) + message_length(joined) + 2 > MAX_MSG:
                    messages.append(current)
                    current = joined
                else:
                    current += "\n\n" + joined
                continue
            for line in block:
                if message_length(current) + message_length(line) + 1 > MAX_MSG:
                    messages.append(current)
                    current = line
                else:
                    current += "\n" + line
    messages.append(current)
    if len(messages) > 1:
        return [f"{message}\n\n({index}/{len(messages)})" for index, message in enumerate(messages, 1)]
    return messages


def build(items, when):
    """기업별 브리핑을 텔레그램 HTML 메시지로 만든다."""
    groups = {}
    seen = set()
    for text in items:
        report = parse_disclosure(text)
        identity = report.url or text.strip()
        if identity in seen:
            continue
        seen.add(identity)
        key = ("company", label_key(report.company)) if report.company else ("report", identity)
        groups.setdefault(key, []).append(report)

    count = sum(len(group) for group in groups.values())
    companies = sum(key[0] == "company" for key in groups)
    company_count = f"{companies}개사 " if companies and all(key[0] == "company" for key in groups) else ""
    head = f"📢 {when.month}/{when.day}({DAYS[when.weekday()]}) 공시 브리핑 · {company_count}{count}건"
    scores = {key: ranking(group) for key, group in groups.items()}
    ranked = sorted((key for key, score in scores.items() if score != (0, 0)),
                    key=scores.__getitem__, reverse=True)[:3]
    remaining = [key for key in groups if key not in ranked]
    sections = []
    for title, keys in (("🔥 오늘의 핵심", ranked), ("그 외 공시" if ranked else "", remaining)):
        blocks = [company_lines(groups[key]) for key in keys]
        if title and blocks:
            blocks[0].insert(0, f"<b>{title}</b>\n")
        sections.append(blocks)
    return pack_messages(head, sections)


def main():
    # offset 없이 읽으면 확인 처리(삭제)되지 않음 → /정리가 없으면 그대로 둠
    updates = call("getUpdates", limit=100, allowed_updates=json.dumps(["message"]))
    msgs = [(u["update_id"], u["message"]) for u in updates if "message" in u]
    triggers = [(uid, m) for uid, m in msgs if text_of(m) in TRIGGERS]
    if not triggers:
        print(f"대기 중인 메시지 {len(msgs)}건, /정리 없음")
        return

    last_trigger = max(uid for uid, _ in triggers)
    done_chats = set()
    for uid, m in sorted(triggers, key=lambda x: x[0], reverse=True):
        chat = m["chat"]["id"]
        if chat in done_chats:
            continue
        done_chats.add(chat)
        items = [text_of(mm) for u2, mm in msgs
                 if mm["chat"]["id"] == chat and u2 < uid and len(text_of(mm)) >= 6 and text_of(mm) not in TRIGGERS]
        when = datetime.datetime.fromtimestamp(m["date"], KST)
        if not items:
            call("sendMessage", chat_id=chat, text="정리할 공시가 없어요. 공시 내용을 먼저 보낸 뒤 /정리 를 보내 주세요.")
        else:
            for t in build(items, when):
                call("sendMessage", chat_id=chat, text=t, parse_mode="HTML", disable_web_page_preview="true")
        print(f"정리본 전송: {len(items)}건")

    # 마지막 /정리까지 처리 완료로 표시 → 텔레그램에서 지워짐. 그 뒤에 온 메시지는 다음 /정리 때 처리
    call("getUpdates", offset=last_trigger + 1, limit=1)


if __name__ == "__main__":
    main()
