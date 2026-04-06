import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from config import DEFAULT_ROOM_NAME

# 예시 형식:
# 2026년 4월 6일 오전 10:12, 닉네임 : 메시지
LINE_PATTERN = re.compile(
    r"^(?P<date>\d{4}년 \d{1,2}월 \d{1,2}일)\s(?P<ampm>오전|오후)\s(?P<time>\d{1,2}:\d{2}),\s(?P<user>.+?)\s:\s(?P<message>.*)$"
)

DATE_HEADER_PATTERN = re.compile(
    r"^\d{4}년 \d{1,2}월 \d{1,2}일"
)


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


def infer_room_name(file_path: Path) -> str:
    # 파일명으로 기본 방 이름 추정
    return file_path.stem or DEFAULT_ROOM_NAME


def parse_chat_text(text: str, source_file: str, room_name: Optional[str] = None) -> List[Dict]:
    room = room_name or DEFAULT_ROOM_NAME
    lines = text.splitlines()

    rows: List[Dict] = []
    current = None

    for raw_line in lines:
        line = raw_line.rstrip()

        # 완전 빈 줄도 메시지 줄바꿈으로 취급 가능
        match = LINE_PATTERN.match(line)
        if match:
            if current:
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
            # 날짜 구분 헤더/시스템 문구는 필요시 무시
            # 멀티라인 메시지면 이전 메시지에 이어붙임
            if current is not None:
                extra = line.strip()
                if extra:
                    current["message"] += "\n" + extra

    if current:
        rows.append(current)

    return rows


def parse_chat_file(file_path: Path, text: str) -> List[Dict]:
    room_name = infer_room_name(file_path)
    return parse_chat_text(
        text=text,
        source_file=file_path.name,
        room_name=room_name,
    )
