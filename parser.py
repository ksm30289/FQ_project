import re
from datetime import datetime
from typing import Dict, List, Optional

from config import DEFAULT_ROOM_NAME, IGNORE_SYSTEM_MESSAGES

LINE_PATTERN = re.compile(
    r"^(?P<date>\d{4}년 \d{1,2}월 \d{1,2}일)\s(?P<ampm>오전|오후)\s(?P<time>\d{1,2}:\d{2}),\s(?P<user>.+?)\s:\s(?P<message>.*)$"
)

SYSTEM_PATTERNS = [
    re.compile(r"^.+님이 들어왔습니다\.$"),
    re.compile(r"^.+님이 나갔습니다\.$"),
    re.compile(r"^.+님을 내보냈습니다\.$"),
]


def parse_kakao_datetime(date_str: str, ampm: str, time_str: str) -> datetime:
    date_part = datetime.strptime(date_str, "%Y년 %m월 %d일")
    hour, minute = map(int, time_str.split(":"))

    if ampm == "오전":
        if hour == 12:
            hour = 0
    elif ampm == "오후":
        if hour != 12:
            hour += 12

    return datetime(
        year=date_part.year,
        month=date_part.month,
        day=date_part.day,
        hour=hour,
        minute=minute,
    )


def is_system_message(message: str) -> bool:
    return any(p.match(message.strip()) for p in SYSTEM_PATTERNS)


def parse_chat_text(
    text: str,
    source_file: str,
    room_name: Optional[str] = None,
) -> List[Dict]:
    room = room_name or DEFAULT_ROOM_NAME
    rows: List[Dict] = []
    current = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        match = LINE_PATTERN.match(line)
        if match:
            if current:
                if not (IGNORE_SYSTEM_MESSAGES and is_system_message(current["message"])):
                    rows.append(current)

            dt = parse_kakao_datetime(
                match.group("date"),
                match.group("ampm"),
                match.group("time"),
            )

            current = {
                "room_name": room,
                "source_file": source_file,
                "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "date": dt.strftime("%Y-%m-%d"),
                "time": dt.strftime("%H:%M:%S"),
                "user_name": match.group("user").strip(),
                "message": match.group("message").strip(),
                "raw_line": line,
            }
        else:
            if current is not None:
                extra = line.strip()
                if extra:
                    current["message"] += "\n" + extra

    if current:
        if not (IGNORE_SYSTEM_MESSAGES and is_system_message(current["message"])):
            rows.append(current)

    return rows
