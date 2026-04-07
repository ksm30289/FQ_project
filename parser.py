import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import DEFAULT_ROOM_NAME, IGNORE_SYSTEM_MESSAGES

# 일반 메시지
# 예:
# 2026. 3. 24. 오전 8:39, 2서버/도우기 : 로얄길드 부길마 이신가요?
MESSAGE_PATTERN = re.compile(
    r"""^
    (?P<year>\d{4})\.\s*
    (?P<month>\d{1,2})\.\s*
    (?P<day>\d{1,2})\.\s*
    (?P<ampm>오전|오후)\s*
    (?P<hour>\d{1,2}):(?P<minute>\d{2}),
    \s*(?P<user>.+?)\s*:\s*(?P<message>.*)
    $""",
    re.VERBOSE,
)

# 시스템 메시지
# 예:
# 2026. 3. 23. 오후 8:36: 2서버/고장난컴퓨터님이 들어왔습니다.
# 2026. 4. 6. 오전 12:07: 관리자가 메시지를 가렸습니다.
SYSTEM_PATTERN = re.compile(
    r"""^
    (?P<year>\d{4})\.\s*
    (?P<month>\d{1,2})\.\s*
    (?P<day>\d{1,2})\.\s*
    (?P<ampm>오전|오후)\s*
    (?P<hour>\d{1,2}):(?P<minute>\d{2})
    :\s*(?P<message>.*)
    $""",
    re.VERBOSE,
)

# 날짜 헤더
# 예: 2026년 3월 23일 월요일
DATE_HEADER_PATTERN = re.compile(
    r"^\d{4}년\s*\d{1,2}월\s*\d{1,2}일\s*\S+$"
)

# 파일 메타 줄
# 예:
# Talk_2026.4.6 10:48-1.txt
# 저장한 날짜 : 2026. 4. 6. 오전 11:31
SAVED_AT_PATTERN = re.compile(r"^저장한 날짜\s*:\s*.+$")
EXPORT_FILENAME_PATTERN = re.compile(r"^Talk_.+\.txt$")


def parse_kakao_datetime(
    year: str,
    month: str,
    day: str,
    ampm: str,
    hour: str,
    minute: str,
) -> datetime:
    y = int(year)
    m = int(month)
    d = int(day)
    h = int(hour)
    mm = int(minute)

    if ampm == "오전":
        if h == 12:
            h = 0
    elif ampm == "오후":
        if h != 12:
            h += 12

    return datetime(y, m, d, h, mm)


def infer_room_name(file_path: Path) -> str:
    return file_path.stem or DEFAULT_ROOM_NAME


def is_metadata_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if DATE_HEADER_PATTERN.match(stripped):
        return True
    if SAVED_AT_PATTERN.match(stripped):
        return True
    if EXPORT_FILENAME_PATTERN.match(stripped):
        return True
    return False


def build_message_row(
    room_name: str,
    source_file: str,
    dt: datetime,
    user_name: str,
    message: str,
    raw_line: str,
) -> Dict:
    clean_user_name = user_name.strip()
    clean_message = message.strip()

    base = f"{dt.strftime('%Y-%m-%d %H:%M:%S')}|{clean_user_name}|{clean_message}"
    row_hash = hashlib.sha1(base.encode("utf-8")).hexdigest()

    return {
        "room_name": room_name,
        "source_file": source_file,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "user_name": clean_user_name,
        "message": clean_message,
        "row_hash": row_hash,
        "raw_line": raw_line,
        "is_system": False,
    }


def build_system_row(
    room_name: str,
    source_file: str,
    dt: datetime,
    message: str,
    raw_line: str,
) -> Dict:
    clean_message = message.strip()

    base = f"{dt.strftime('%Y-%m-%d %H:%M:%S')}|SYSTEM|{clean_message}"
    row_hash = hashlib.sha1(base.encode("utf-8")).hexdigest()

    return {
        "room_name": room_name,
        "source_file": source_file,
        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "user_name": "SYSTEM",
        "message": clean_message,
        "row_hash": row_hash,
        "raw_line": raw_line,
        "is_system": True,
    }


def parse_chat_text(
    text: str,
    source_file: str,
    room_name: Optional[str] = None,
) -> List[Dict]:
    room = room_name or DEFAULT_ROOM_NAME
    rows: List[Dict] = []
    current: Optional[Dict] = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if is_metadata_line(stripped):
            continue

        msg_match = MESSAGE_PATTERN.match(stripped)
        if msg_match:
            # 기존 메시지 flush
            if current is not None:
                if not (IGNORE_SYSTEM_MESSAGES and current.get("is_system")):
                    rows.append(current)

            dt = parse_kakao_datetime(
                msg_match.group("year"),
                msg_match.group("month"),
                msg_match.group("day"),
                msg_match.group("ampm"),
                msg_match.group("hour"),
                msg_match.group("minute"),
            )

            user_name = msg_match.group("user").strip()

            # 오픈채팅봇 제외
            if "오픈채팅봇" in user_name:
                current = None
                continue

            current = build_message_row(
                room_name=room,
                source_file=source_file,
                dt=dt,
                user_name=user_name,
                message=msg_match.group("message"),
                raw_line=stripped,
            )
            continue

        sys_match = SYSTEM_PATTERN.match(stripped)
        if sys_match:
            if current is not None:
                if not (IGNORE_SYSTEM_MESSAGES and current.get("is_system")):
                    rows.append(current)

            dt = parse_kakao_datetime(
                sys_match.group("year"),
                sys_match.group("month"),
                sys_match.group("day"),
                sys_match.group("ampm"),
                sys_match.group("hour"),
                sys_match.group("minute"),
            )

            current = build_system_row(
                room_name=room,
                source_file=source_file,
                dt=dt,
                message=sys_match.group("message"),
                raw_line=stripped,
            )
            continue

        # 멀티라인 메시지 처리
        if current is not None and stripped:
            current["message"] += "\n" + stripped

    if current is not None:
        if not (IGNORE_SYSTEM_MESSAGES and current.get("is_system")):
            rows.append(current)

    return rows


def parse_chat_file(file_path: Path, text: str) -> List[Dict]:
    room_name = infer_room_name(file_path)
    return parse_chat_text(
        text=text,
        source_file=file_path.name,
        room_name=room_name,
    )
