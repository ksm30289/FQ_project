import re
from typing import Dict


# =========================
# 키워드 정의
# =========================
GAME_POSITIVE_KEYWORDS = [
    "재밌", "재미", "재미있", "꿀잼", "좋아요", "좋다", "최고", "만족", "갓겜",
    "업데이트", "패치", "이벤트", "보상", "운영", "개선", "편의성", "혜자",
    "아이템", "장비", "스킬", "던전", "레이드", "사냥", "성장", "강화",
]

GAME_NEGATIVE_KEYWORDS = [
    "버그", "렉", "튕", "튕김", "팅김", "오류", "문제", "불편", "짜증", "최악",
    "노잼", "망겜", "개같", "다신안", "다신 안", "안됨", "안 돼", "최적화", "창렬",
    "과금", "밸런스", "너프", "하향", "상향", "시발", "씨발", "지랄", "병신",
    "아이템", "장비", "스킬", "던전", "레이드", "사냥", "강화", "호구"
]

GAME_SUGGESTION_KEYWORDS = [
    "해줬으면", "해주세요", "추가", "개선", "수정", "바꿔", "바꿔줘", "좋겠다",
    "필요", "부탁", "원함", "원한다", "있으면 좋겠",
    "상향", "하향", "너프", "버프",
    "패치", "업데이트", "이벤트", "보상", "편의성",
]

GAME_DOMAIN_KEYWORDS = [
    "게임", "운영", "업데이트", "패치", "이벤트", "보상", "점검", "공지",
    "서버", "계정", "로그인", "접속", "결제", "과금",
    "아이템", "장비", "스킬", "직업", "클래스", "밸런스", "강화",
    "던전", "레이드", "사냥", "길드", "퀘스트", "몬스터", "보스",
    "드랍", "드롭", "재화", "골드", "다이아", "쿠폰",
    "버그", "렉", "오류", "최적화",
]

NOISE_EXACT_WORDS = {
    "ㅇㅇ", "ㅇㅎ", "ㄱㄱ", "ㄴㄴ", "ㄷㄷ",
    "ㅋㅋ", "ㅋㅋㅋ", "ㅋㅋㅋㅋ",
    "ㅎㅎ", "ㅎㅎㅎ",
    "와", "헐", "오",
    "굿", "굿굿",
    "ㅊㅊ", "ㄹㅇ",
    "인정", "ㅅㅅ",
}

CHAT_ADMIN_PATTERNS = [
    r"기본닉.*변경",
    r"닉.*변경",
    r"닉네임.*변경",
    r"닉변",
    r"오픈채팅",
    r"공지방",
    r"방제",
    r"방 이름",
    r"매니저",
    r"부매니저",
    r"강퇴",
    r"추방",
]

TRADE_PATTERNS = [
    r"팝니다",
    r"삽니다",
    r"판매",
    r"구매",
    r"매입",
    r"매물",
    r"가격",
    r"시세",
    r"얼마에",
    r"흥정",
    r"ㅍㅍ",
    r"ㅅㅅ",
]

RECRUIT_PATTERNS = [
    r"길드.*모집",
    r"모집합니다",
    r"모셔요",
    r"오세요",
    r"가입.*문의",
    r"단톡",
    r"톡방",
    r"인원 모집",
]


EMOJI_ONLY_PATTERN = re.compile(r"^[\W_]+$")
REPEAT_CHAR_PATTERN = re.compile(r"^(.)\1{2,}$")


# =========================
# 내부 유틸
# =========================
def _normalize_message(message: str) -> str:
    msg = str(message or "").strip().lower()
    msg = re.sub(r"\s+", " ", msg)
    return msg


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _matches_any_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


# =========================
# 노이즈 필터
# =========================
def is_noise_message(message: str) -> bool:
    msg = _normalize_message(message)

    if not msg:
        return True

    if len(msg) <= 1:
        return True

    if msg in NOISE_EXACT_WORDS:
        return True

    if len(msg) <= 4 and REPEAT_CHAR_PATTERN.match(msg):
        return True

    if EMOJI_ONLY_PATTERN.match(msg):
        return True

    if _matches_any_pattern(msg, CHAT_ADMIN_PATTERNS):
        return True

    if _matches_any_pattern(msg, TRADE_PATTERNS):
        return True

    if _matches_any_pattern(msg, RECRUIT_PATTERNS):
        return True

    return False


# =========================
# 게임 관련 필터 (핵심)
# =========================
def is_game_related_message(message: str) -> bool:
    msg = _normalize_message(message)

    if not msg:
        return False

    if is_noise_message(msg):
        return False

    # 강한 필터 (핵심 피드백 중심)
    strong_keywords = (
        GAME_NEGATIVE_KEYWORDS
        + GAME_SUGGESTION_KEYWORDS
        + ["운영", "업데이트", "패치", "이벤트", "보상", "버그", "렉", "오류", "밸런스"]
    )

    if _contains_any(msg, strong_keywords):
        return True

    # 약한 필터 (긍정/일반)
    if _contains_any(msg, GAME_POSITIVE_KEYWORDS):
        return True

    if _contains_any(msg, GAME_DOMAIN_KEYWORDS):
        return True

    return False


# =========================
# 최종 필터
# =========================
def should_keep_for_trend(row: Dict[str, str]) -> bool:
    message = row.get("message", "")
    return is_game_related_message(message)
