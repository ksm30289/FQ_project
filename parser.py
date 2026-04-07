import re
from typing import List, Dict

from config import EXCLUDED_USERNAMES, IGNORE_SYSTEM_MESSAGES


DATE_LINE_PATTERN = re.compile(
    r"^(\d{4})년\s+(\d{1,2})월\s+(\d{1,2})일\s+(오전|오후)\s+(\d{1,2}):(\d{2}),\s*(.+?)\s*:\s*(.*)$"
)

SYSTEM_MESSAGE_PATTERNS = [
    re.compile(r"^.*님이 들어왔습니다\.$"),
    re.compile(r"^.*님이 나갔습니다\.$"),
    re.compile(r"^.*님을 초대했습니다\.$"),
    re.compile(r"^채팅방 관리자가 .*"),
    re.compile(r"^운영정책을 위반한 메시지로 신고 접수.*"),
]


def _normalize_user(user: str) -> str:
    return str(user).strip()


def _is_excluded_user(user: str) -> bool:
    normalized = _normalize_user(user)
    return normalized in {_normalize_user(x) for x in EXCLUDED_USERNAMES}


def _is_system_message(message: str) -> bool:
    msg = str(message).strip()
    for pattern in SYSTEM_MESSAGE_PATTERNS:
        if pattern.match(msg):
            return True
    return False


def _to_24h(ampm: str, hour: int) -> str:
    if ampm == "오전":
        if hour == 12:
            hour = 0
    elif ampm == "오후":
        if hour != 12:
            hour += 12
    return f"{hour:02d}"


def parse_chat_text(text: str, source_file_name: str = "") -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    if not text or not str(text).strip():
        return rows

    current_row = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        match = DATE_LINE_PATTERN.match(line)

        if match:
            year, month, day, ampm, hour, minute, user, message = match.groups()

            user = _normalize_user(user)
            message = str(message).strip()

            if _is_excluded_user(user):
                current_row = None
                continue

            if IGNORE_SYSTEM_MESSAGES and _is_system_message(message):
                current_row = None
                continue

            hh = _to_24h(ampm, int(hour))
            date_str = f"{year}-{int(month):02d}-{int(day):02d}"
            time_str = f"{hh}:{minute}"

            current_row = {
                "date": date_str,
                "time": time_str,
                "user": user,
                "message": message,
                "source_file_name": source_file_name,
            }
            rows.append(current_row)

        else:
            # 멀티라인 메시지 이어붙이기
            if current_row is not None:
                extra = line.strip()
                if extra:
                    current_row["message"] = f"{current_row['message']}\n{extra}"

    return rows
