import re
from typing import List, Dict, Optional, Set

from config import EXCLUDED_USERNAMES, IGNORE_SYSTEM_MESSAGES
from utils import make_row_hash


CHAT_LINE_PATTERN = re.compile(
    r"^(\d{4}\.\s?\d{1,2}\.\s?\d{1,2}\.\s(?:오전|오후)\s\d{1,2}:\d{2}),\s(.+?)\s:\s(.*)$"
)


def _normalize_datetime(raw_dt: str) -> str:
    # 지금은 원문 유지
    # 필요하면 나중에 YYYY-MM-DD HH:MM:SS 형태로 변환 가능
    return raw_dt.strip()


def _is_system_message(message: str) -> bool:
    system_keywords = [
        "님이 들어왔습니다.",
        "님이 나갔습니다.",
        "님을 내보냈습니다.",
        "운영정책을 위반한 메시지로 신고 접수",
        "가려진 메시지입니다",
    ]
    return any(keyword in message for keyword in system_keywords)


def parse_chat_text(
    text: str,
    existing_row_hashes: Optional[Set[str]] = None,
    source_file: str = "",
) -> List[Dict]:
    if existing_row_hashes is None:
        existing_row_hashes = set()

    parsed_rows = []

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = CHAT_LINE_PATTERN.match(line)
        if not match:
            continue

        raw_datetime, user, message = match.groups()

        user = user.strip()
        message = message.strip()
        datetime_str = _normalize_datetime(raw_datetime)

        if not user or not message:
            continue

        if user in EXCLUDED_USERNAMES:
            continue

        if IGNORE_SYSTEM_MESSAGES and _is_system_message(message):
            continue

        row_hash = make_row_hash(datetime_str, user, message)

        if row_hash in existing_row_hashes:
            continue

        existing_row_hashes.add(row_hash)

        parsed_rows.append({
            "datetime": datetime_str,
            "user": user,
            "message": message,
            "row_hash": row_hash,
            "source_file": source_file,
        })

    return parsed_rows
