import re
from datetime import datetime

# 카카오톡 기본 메시지 시작 패턴 예시:
# 2026. 4. 6. 오후 8:29, 닉네임 : 메시지
#
# 핵심:
# - 메시지 시작 줄만 빠르게 판별
# - 멀티라인 메시지는 이전 메시지에 이어붙임
# - 불필요한 datetime 변환 최소화

MESSAGE_START_RE = re.compile(
    r"^(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*(오전|오후)\s*\d{1,2}:\d{2}),\s*(.*?)\s*:\s*(.*)$"
)

SYSTEM_KEYWORDS = (
    "님이 들어왔습니다.",
    "님이 나갔습니다.",
    "님을 내보냈습니다.",
    "방장이",
    "운영정책을",
    "채팅방 이름을",
    "사진을 변경했습니다.",
    "파일:",
    "삭제된 메시지입니다.",
)

EXCLUDED_USERNAMES = {"오픈채팅봇"}


def normalize_datetime(dt_str: str) -> str:
    """
    카톡 날짜 문자열 -> YYYY-MM-DD HH:MM:SS
    예: 2026. 4. 6. 오후 8:29
    """
    try:
        # 빠른 파싱용 전처리
        s = dt_str.replace("  ", " ").strip()
        date_part, time_part = s.rsplit(" ", 2)[0], " ".join(s.rsplit(" ", 2)[1:])

        # 직접 분해
        # ex) '2026. 4. 6.' + '오후 8:29'
        parts = s.split()
        year = int(parts[0].replace(".", ""))
        month = int(parts[1].replace(".", ""))
        day = int(parts[2].replace(".", ""))
        ampm = parts[3]
        hh, mm = parts[4].split(":")
        hh = int(hh)
        mm = int(mm)

        if ampm == "오후" and hh != 12:
            hh += 12
        elif ampm == "오전" and hh == 12:
            hh = 0

        dt = datetime(year, month, day, hh, mm)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str


def is_system_message(message: str) -> bool:
    return any(k in message for k in SYSTEM_KEYWORDS)


def parse_chat_text(text: str):
    """
    반환 형식:
    [
        {
            "datetime": "2026-04-06 20:29:00",
            "user": "닉네임",
            "message": "내용",
        },
        ...
    ]
    """

    rows = []
    current = None

    # splitlines()가 일반 split("\n")보다 안전
    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        m = MESSAGE_START_RE.match(line)
        if m:
            # 이전 메시지 저장
            if current:
                if (
                    current["user"] not in EXCLUDED_USERNAMES
                    and current["message"]
                    and not is_system_message(current["message"])
                ):
                    rows.append(current)

            dt_raw, _, user, message = m.groups()
            current = {
                "datetime": normalize_datetime(dt_raw),
                "user": user.strip(),
                "message": message.strip(),
            }
        else:
            # 멀티라인 메시지 이어붙이기
            if current:
                if current["message"]:
                    current["message"] += "\n" + line
                else:
                    current["message"] = line

    # 마지막 메시지 저장
    if current:
        if (
            current["user"] not in EXCLUDED_USERNAMES
            and current["message"]
            and not is_system_message(current["message"])
        ):
            rows.append(current)

    return rows
