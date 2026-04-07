import re
from typing import Dict, List, Optional

from config import EXCLUDED_USERNAMES, IGNORE_SYSTEM_MESSAGES, DEBUG_LOG


DATE_LINE_PATTERNS = [
    re.compile(
        r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(오전|오후)\s+(\d{1,2}):(\d{2}),\s*(.+?)\s*:\s*(.*)$"
    ),
    re.compile(
        r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s+(\d{1,2}):(\d{2}),\s*(.+?)\s*:\s*(.*)$"
    ),
]

HEADER_PATTERNS = [
    re.compile(r"^카카오톡 대화$"),
    re.compile(r"^저장한 날짜\s*:\s*.*$"),
    re.compile(r"^Talk_.*\.txt$"),
    re.compile(r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*.*$"),
]

SYSTEM_MESSAGE_PATTERNS = [
    re.compile(r"^.*님이 들어왔습니다\.$"),
    re.compile(r"^.*님이 나갔습니다\.$"),
    re.compile(r"^.*님을 초대했습니다\.$"),
    re.compile(r"^.*님이 강퇴되었습니다\.$"),
    re.compile(r"^채팅방 관리자가 .*"),
    re.compile(r"^운영정책을 위반한 메시지로 신고 접수.*"),
    re.compile(r"^메시지를 가렸습니다\.$"),
    re.compile(r"^삭제된 메시지입니다\.$"),
    re.compile(r"^사진(?: \d+장)?$"),
    re.compile(r"^동영상$"),
    re.compile(r"^이모티콘$"),
    re.compile(r"^파일: .*"),
]


def log_debug(msg: str) -> None:
    if DEBUG_LOG:
        print(msg)


def _normalize_text(value: str) -> str:
    return str(value).strip()


def _normalize_user(user: str) -> str:
    user = _normalize_text(user)
    user = re.sub(r"\s*/\s*", "/", user)
    user = re.sub(r"\s+", " ", user).strip()
    return user


def _build_excluded_usernames_set() -> set:
    normalized = set()
    for x in EXCLUDED_USERNAMES:
        name = _normalize_user(str(x))
        if name:
            normalized.add(name)
    return normalized


EXCLUDED_USERNAMES_SET = _build_excluded_usernames_set()


def _is_header_line(line: str) -> bool:
    text = _normalize_text(line)
    if not text:
        return False

    for pattern in HEADER_PATTERNS:
        if pattern.match(text):
            return True
    return False


def _is_excluded_user(user: str) -> bool:
    return _normalize_user(user) in EXCLUDED_USERNAMES_SET


def _is_system_message(message: str) -> bool:
    text = _normalize_text(message)
    if not text:
        return False

    for pattern in SYSTEM_MESSAGE_PATTERNS:
        if pattern.match(text):
            return True
    return False


def _to_24h(ampm: str, hour: int) -> int:
    if ampm == "오전":
        return 0 if hour == 12 else hour
    if ampm == "오후":
        return 12 if hour == 12 else hour + 12
    return hour


def _parse_date_line(line: str) -> Optional[Dict[str, str]]:
    text = line.rstrip()

    for pattern in DATE_LINE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue

        year, month, day, ampm, hour, minute, user, message = match.groups()

        month_i = int(month)
        day_i = int(day)
        hour_i = _to_24h(ampm, int(hour))

        return {
            "date": f"{int(year):04d}-{month_i:02d}-{day_i:02d}",
            "time": f"{hour_i:02d}:{int(minute):02d}",
            "user": _normalize_user(user),
            "message": str(message).strip(),
        }

    return None


def parse_chat_text(text: str, source_file_name: str = "") -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    if not text or not str(text).strip():
        log_debug("[PARSER] 빈 텍스트")
        return rows

    lines = text.splitlines()
    log_debug(f"[PARSER] source_file_name={source_file_name}")
    log_debug(f"[PARSER] 전체 라인 수={len(lines)}")
    log_debug(f"[PARSER] 첫 5줄 샘플={repr(lines[:5])}")

    current_row: Optional[Dict[str, str]] = None
    matched_count = 0
    unmatched_samples = []

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip().lstrip("\ufeff").replace("\u200b", "").replace("\xa0", " ")

        if not line:
            continue

        if _is_header_line(line):
            continue

        parsed = _parse_date_line(line)

        if parsed is not None:
            matched_count += 1
            user = parsed["user"]
            message = parsed["message"]

            if _is_excluded_user(user):
                current_row = None
                continue

            if IGNORE_SYSTEM_MESSAGES and _is_system_message(message):
                current_row = None
                continue

            current_row = {
                "date": parsed["date"],
                "time": parsed["time"],
                "user": user,
                "message": message,
                "source_file_name": source_file_name,
            }
            rows.append(current_row)
            continue

        if len(unmatched_samples) < 10:
            unmatched_samples.append((idx, line))

        if current_row is not None:
            current_row["message"] = f"{current_row['message']}\n{line}"

    log_debug(f"[PARSER] 날짜 패턴 매치 수={matched_count}")
    log_debug(f"[PARSER] 최종 rows 수={len(rows)}")
    log_debug(f"[PARSER] unmatched 샘플={unmatched_samples}")

    return rows
