"""텔레그램 공시 정리 봇 (@Be_Known_News_bot)

사용법: 봇에게 공시 내용을 보내 두고, 정리하고 싶을 때 `/정리`를 보내면
그때까지 보낸 메시지를 유형별로 묶은 정리본을 같은 대화창으로 보내 준다.

- GitHub Actions(.github/workflows/telegram-digest.yml)가 몇 분마다 이 스크립트를 실행한다.
- AI 없이 단어 기준으로만 분류한다. 내용은 저장하지 않고, 로그에도 내용을 남기지 않는다.
- 텔레그램은 봇이 받은 메시지를 최대 24시간만 보관하므로, 보낸 지 24시간 안에 `/정리`를 해야 한다.
- 대화창(chat)별로 따로 정리한다. 다른 사람이 봇에게 보낸 메시지가 내 정리본에 섞이지 않는다.

필요: 환경변수 TELEGRAM_BOT_TOKEN
"""
import datetime
import json
import os
import urllib.parse
import urllib.request

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}/"
TRIGGERS = {"/정리", "정리", "/summary", "/digest"}
KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = "월화수목금토일"

# 위에서부터 먼저 맞는 유형으로 분류 (단어가 하나라도 들어 있으면)
CATEGORIES = [
    ("📌 수주·공급계약", ["공급계약", "판매계약", "수주", "단일판매", "납품계약"]),
    ("💰 증자·CB·BW", ["유상증자", "무상증자", "전환사채", "신주인수권", "교환사채", "제3자배정", "CB", "BW", "감자"]),
    ("🔁 자사주", ["자기주식", "자사주", "소각"]),
    ("📊 실적", ["잠정", "실적", "영업이익", "매출액", "손익구조", "순이익"]),
    ("🤝 M&A·지분", ["최대주주", "인수", "합병", "양수", "양도", "지분", "타법인", "분할"]),
    ("💵 배당", ["배당"]),
    ("⚠️ 주의", ["소송", "횡령", "배임", "거래정지", "관리종목", "상장폐지", "불성실", "감사의견"]),
]
OTHER = "📎 기타"
MAX_ITEM = 700     # 한 건당 최대 글자 수
MAX_MSG = 3800     # 텔레그램 메시지 한 개 최대 4096자 → 여유 있게 나눔


def call(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(API + method, data), timeout=30) as r:
        res = json.load(r)
    if not res.get("ok"):
        raise RuntimeError(f"{method} 실패: {res.get('description')}")
    return res["result"]


def text_of(msg):
    return (msg.get("text") or msg.get("caption") or "").strip()


def classify(text):
    for name, words in CATEGORIES:
        if any(w in text for w in words):
            return name
    return OTHER


def build(items, when):
    """items: [텍스트] → 텔레그램 메시지 목록 (길면 여러 개로 나눔)"""
    groups = {}
    for t in items:
        groups.setdefault(classify(t), []).append(t if len(t) <= MAX_ITEM else t[:MAX_ITEM] + "…")
    order = [c[0] for c in CATEGORIES] + [OTHER]
    head = f"📢 {when.month}/{when.day}({DAYS[when.weekday()]}) 공시 정리 · 총 {len(items)}건"
    blocks = []
    for name in order:
        if name not in groups:
            continue
        lines = [f"\n{name} ({len(groups[name])})"]
        lines += ["• " + t.replace("\n", "\n   ") for t in groups[name]]
        blocks.append("\n".join(lines))
    msgs, cur = [], head
    for b in blocks:
        if len(cur) + len(b) + 1 > MAX_MSG:
            msgs.append(cur)
            cur = b.lstrip("\n")
        else:
            cur += "\n" + b
    msgs.append(cur)
    if len(msgs) > 1:
        msgs = [f"{m}\n\n({i + 1}/{len(msgs)})" for i, m in enumerate(msgs)]
    return msgs


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
                call("sendMessage", chat_id=chat, text=t, disable_web_page_preview="true")
        print(f"정리본 전송: {len(items)}건")

    # 마지막 /정리까지 처리 완료로 표시 → 텔레그램에서 지워짐. 그 뒤에 온 메시지는 다음 /정리 때 처리
    call("getUpdates", offset=last_trigger + 1, limit=1)


if __name__ == "__main__":
    main()
