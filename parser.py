import re
from typing import Dict, List, Optional

from config import EXCLUDED_USERNAMES, IGNORE_SYSTEM_MESSAGES


# =====================================
# 카카오톡 내보내기 포맷 지원
# 1) 2026. 4. 7. 오후 7:50, 사용자 : 메시지
# 2) 2026년 4월 7일 오후 7:50, 사용자 : 메시지
# =====================================
DATE_LINE_PATTERNS = [
    re.compile(
        r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(오전|오후)\s+(\d{1,2}):(\d{2}),\s*(.+?)\s*:\s*(.*)$"
    ),
    re.compile(
        r"^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s+(\d{1,2}):(\d{2}),\s*(.+?)\s*:\s*(.*)$"
    ),
]


# =====================================
# 무시할 헤더/안내 줄
# =====================================
HEADER_PATTERNS = [
    re.compile(r"^카카오톡 대화$"),
    re.compile(r"^저장한 날짜\s*:\s*.*$"),
]


# =====================================
# 시스템 메시지 패턴
# 필요하면 여기에 계속 추가 가능
# =====================================
SYSTEM_MESSAGE_PATTERNS = [
    re.compile(r"^.*님이 들어왔습니다\.$"),
    re.compile(r"^.*님이 나갔습니다\.$"),
    re.compile(r"^.*님을 초대했습니다\.$"),
    re.compile(r"^.*님이 강퇴되었습니다\.$"),
    re.compile(r"^채팅방 관리자가 .*"),
    re.compile(r"^운영정책을 위반한 메시지로 신고 접수.*"),
    re.compile(r"^메시지를 가렸습니다\.$"),
    re.compile(r"^삭제된 메시지입니다\.$"),
    re.compile(r"^사진 \d+장$"),
    re.compile(r"^동영상$"),
    re.compile(r"^이모티콘$"),
    re.compile(r"^파일: .*"),
]


def _normalize_text(value: str) -> str:
    return str(value).strip()


def _normalize_user(user: str) -> str:
    user = _normalize_text(user)
    # "3서버 / 와일드바" -> "3서버/와일드바"
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
        return rows

    current_row: Optional[Dict[str, str]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")

        if not line.strip():
            continue

        if _is_header_line(line):
            continue

        parsed = _parse_date_line(line)

        if parsed is not None:
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

        # 날짜 패턴이 아니면 이전 메시지의 멀티라인으로 간주
        if current_row is not None:
            extra = line.strip()
            if extra:
                current_row["message"] = f"{current_row['message']}\n{extra}"

    return rows
