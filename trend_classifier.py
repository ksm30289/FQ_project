# trend_classifier.py
import re
import hashlib

TREND_HEADERS = ["날짜", "시간", "유저명", "메시지", "감지 키워드"]

NEGATIVE_KEYWORDS = [
    "별로", "구림", "병신", "망겜", "노잼", "재미없", "지루", "불편", "답답", "서버",
    "짜증", "화남", "열받", "실망", "문제", "오류", "버그", "렉", "끊김", "핵", "지랄",
    "튕김", "안됨", "안 돼", "못함", "이상함", "불만", "최악", "삭제", "시발", "씨발",
    "접음", "접을", "탈주", "환불", "아쉽", "귀찮", "빡침", "불쾌", "이슈"
]

POSITIVE_KEYWORDS = [
    "좋다", "좋아요", "좋네", "재밌", "재미있", "꿀잼", "만족", "훌륭",
    "잘했다", "잘했", "칭찬", "감사", "고맙", "최고", "괜찮", "귀엽",
    "예쁘", "멋지", "호감", "갓겜", "할만", "기대", "기대됨", "나쁘지 않",
    "재밌네", "좋은데", "잘 만든", "잘만든"
]

SUGGESTION_KEYWORDS = [
    "건의", "제안", "개선", "추가", "넣어", "넣어줘", "바꿔", "바꿔줘",
    "수정", "고쳐", "고쳐줘", "해줘", "있으면 좋겠", "있었으면",
    "필요", "원함", "원한다", "부탁", "지원해", "지원해줘", "만들어",
    "추가해", "개선해", "부족", "늘려", "줄여", "막아", "가능하게"
]

NEGATIVE_EXCLUDE_PATTERNS = [
    "문제 없다", "문제없다", "안 나쁘", "나쁘지 않", "렉 없다", "렉없",
    "버그 없다", "버그없", "오류 없다", "오류없", "불편하지 않"
]

POSITIVE_EXCLUDE_PATTERNS = [
    "안 좋", "좋은데 문제", "좋은데 렉", "좋은데 버그"
]

SUGGESTION_EXCLUDE_PATTERNS = [
    "해줘서 고마워", "해줘서 감사"
]


def normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def is_meaningful_message(text: str) -> bool:
    text = (text or "").strip()
    return len(text) >= 3


def is_noise_message(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True

    if re.fullmatch(r"[ㅋㅎㅠㅜ!~.\s]+", text):
        return True

    return False


def find_matched_keywords(text: str, keywords: list[str], exclude_patterns: list[str] | None = None) -> list[str]:
    text_norm = normalize_text(text)
    exclude_patterns = exclude_patterns or []

    for pattern in exclude_patterns:
        if pattern in text_norm:
            return []

    matched = [kw for kw in keywords if kw.lower() in text_norm]
    return list(dict.fromkeys(matched))


def classify_message(message: str) -> dict[str, list[str]]:
    if not is_meaningful_message(message):
        return {}

    if is_noise_message(message):
        return {}

    text = normalize_text(message)

    negative_hits = find_matched_keywords(text, NEGATIVE_KEYWORDS, NEGATIVE_EXCLUDE_PATTERNS)
    positive_hits = find_matched_keywords(text, POSITIVE_KEYWORDS, POSITIVE_EXCLUDE_PATTERNS)
    suggestion_hits = find_matched_keywords(text, SUGGESTION_KEYWORDS, SUGGESTION_EXCLUDE_PATTERNS)

    result = {}

    if negative_hits:
        result["negative_trend"] = negative_hits

    if positive_hits:
        result["positive_trend"] = positive_hits

    if suggestion_hits:
        result["suggestions"] = suggestion_hits

    return result


def make_trend_row(row: dict, detected_keywords: list[str]) -> list[str]:
    return [
        row.get("date", ""),
        row.get("time", ""),
        row.get("user_name", ""),
        row.get("message", ""),
        ", ".join(detected_keywords)
    ]


def make_trend_key_from_row_values(date: str, time: str, user_name: str, message: str, sheet_name: str) -> str:
    base = f"{sheet_name}|{date}|{time}|{user_name}|{message}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def make_trend_key_from_raw_row(row: dict, sheet_name: str) -> str:
    return make_trend_key_from_row_values(
        row.get("date", ""),
        row.get("time", ""),
        row.get("user_name", ""),
        row.get("message", ""),
        sheet_name
    )
