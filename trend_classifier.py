# trend_classifier.py
import re
from typing import Dict, List

TREND_HEADERS = ["날짜", "시간", "유저명", "메시지", "감지 키워드", "AI 판정", "AI 사유"]

GAME_CONTEXT_KEYWORDS = [
    "게임", "운영", "이벤트", "보상", "업데이트", "점검", "패치", "마법", "제볼트", "미호",
    "서버", "버그", "렉", "길드", "전투", "던전", "캐릭", "스킬", "카일", "폴린", "카린",
    "밸런스", "과금", "확률", "ui", "컨텐츠", "콘텐츠", "사전예약", "의뢰", "에피소드",
    "보스", "아이템", "강화", "직업", "매칭", "랭크", "채팅", "모험가", "아레나"
]

NEGATIVE_KEYWORDS = [
    "별로", "구림", "병신", "망겜", "노잼", "재미없", "지루", "불편", "답답", "서버", "비싼", "호구",
    "짜증", "화남", "열받", "실망", "문제", "오류", "버그", "렉", "끊김", "핵", "지랄",
    "튕김", "안됨", "안 돼", "못함", "이상함", "불만", "최악", "삭제", "시발", "씨발",
    "접음", "접을", "탈주", "환불", "아쉽", "귀찮", "빡침", "불쾌", "이슈", "창렬"
]

POSITIVE_KEYWORDS = [
    "좋다", "좋아요", "좋네", "재밌", "재미있", "꿀잼", "만족", "훌륭",
    "잘했다", "잘했", "칭찬", "감사", "고맙", "최고", "괜찮", "귀엽",
    "예쁘", "멋지", "호감", "갓겜", "할만", "기대", "기대됨", "나쁘지 않",
    "재밌네", "좋은데", "잘 만든", "잘만든"
]

SUGGESTION_KEYWORDS = [
    "건의", "제안", "개선", "추가", "넣어", "넣어줘", "바꿔", "바꿔줘",
    "수정", "고쳐", "고쳐줘", "해줘", "해주세요", "있으면 좋겠", "있었으면",
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

CHAT_NOISE_PATTERNS = [
    "ㅋㅋ", "ㅎㅎ", "ㄷㄷ", "헐", "와", "오", "ㅇㅇ", "ㄱㄱ", "ㅈㅈ",
    "반갑", "친추", "누구세요", "누구세", "감사합니다", "수고하셨"
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
    if len(text) < 3:
        return True
    if re.fullmatch(r"[ㅋㅎㅠㅜ!~.\s]+", text):
        return True
    return False


def contains_any(text: str, keywords: List[str]) -> List[str]:
    text_norm = normalize_text(text)
    matched = [kw for kw in keywords if kw.lower() in text_norm]
    return list(dict.fromkeys(matched))


def has_exclude_pattern(text: str, patterns: List[str]) -> bool:
    text_norm = normalize_text(text)
    return any(p.lower() in text_norm for p in patterns)


def has_game_context(text: str) -> bool:
    return len(contains_any(text, GAME_CONTEXT_KEYWORDS)) > 0


def is_chatty_message(text: str) -> bool:
    return len(contains_any(text, CHAT_NOISE_PATTERNS)) > 0


def should_send_to_ai(message: str) -> bool:
    text = (message or "").strip()
    if len(text) < 6:
        return False
    if text in ["ㅋㅋ", "ㅎㅎ", "ㅇㅇ", "ㄷㄷ", "헐", "와", "오"]:
        return False
    return True


def classify_message(message: str) -> Dict[str, List[str]]:
    if not is_meaningful_message(message):
        return {}

    if is_noise_message(message):
        return {}

    text = normalize_text(message)

    if is_chatty_message(text) and not has_game_context(text):
        return {}

    negative_hits = contains_any(text, NEGATIVE_KEYWORDS)
    positive_hits = contains_any(text, POSITIVE_KEYWORDS)
    suggestion_hits = contains_any(text, SUGGESTION_KEYWORDS)

    result = {}

    if negative_hits and not has_exclude_pattern(text, NEGATIVE_EXCLUDE_PATTERNS):
        if len(negative_hits) >= 1:
            result["negative_trend"] = negative_hits

    if positive_hits and not has_exclude_pattern(text, POSITIVE_EXCLUDE_PATTERNS):
        if len(positive_hits) >= 1:
            result["positive_trend"] = positive_hits

    if suggestion_hits and not has_exclude_pattern(text, SUGGESTION_EXCLUDE_PATTERNS):
        if len(suggestion_hits) >= 1:
            result["suggestions"] = suggestion_hits

    return result


def make_trend_row(
    row: dict,
    detected_keywords: List[str],
    ai_label: str = "",
    ai_reason: str = ""
) -> List[str]:
    return [
        row.get("date", ""),
        row.get("time", ""),
        row.get("user_name", ""),
        row.get("message", ""),
        ", ".join(detected_keywords),
        ai_label,
        ai_reason,
    ]
