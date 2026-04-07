import json
import os
import re
import time
from typing import Dict, Any, List, Optional

from openai import OpenAI


def _get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"환경변수 누락: {name}")
    return value


OPENAI_API_KEY = _get_env("OPENAI_API_KEY")
OPENAI_MODEL = _get_env("OPENAI_MODEL", "gpt-4o-mini")
AI_REVIEW_ENABLED = _get_env("AI_REVIEW_ENABLED", "true").lower() == "true"
AI_MIN_CONFIDENCE = float(_get_env("AI_MIN_CONFIDENCE", "0.80"))
AI_MAX_RETRIES = int(_get_env("AI_MAX_RETRIES", "3"))
AI_RETRY_SLEEP_SEC = float(_get_env("AI_RETRY_SLEEP_SEC", "1.2"))

client = OpenAI(api_key=OPENAI_API_KEY)


SKIP_EXACT = {
    "ㅋ", "ㅋㅋ", "ㅋㅋㅋ", "ㅋㅋㅋㅋ",
    "ㅎ", "ㅎㅎ", "ㅎㅎㅎ", "ㅎㅎㅎㅎ",
    "ㅠ", "ㅠㅠ", "ㅜ", "ㅜㅜ",
    "ㄷㄷ", "ㅇㅇ", "ㄴㄴ", "ㄱㄱ",
    "네", "넵", "예", "아", "오", "와", "헐", "굿",
    "하이", "안녕", "ㅂㅂ", "잘자", "출첵",
}

SKIP_PATTERNS = [
    r"^[ㅋㅎㅠㅜ]+$",
    r"^[!?~.,\s]+$",
    r"^[0-9\s]+$",
    r"^(네|넵|예|ㅇㅇ|ㄴㄴ|ㄱㄱ|오|와|헐|굿)$",
    r"^(안녕|하이|ㅂㅂ|잘자|출첵)$",
]

QUESTION_HINTS = [
    "?", "어떻게", "왜", "뭐임", "뭔가", "되는거", "되는 거",
    "됨?", "임?", "인가", "있음?", "없음?", "가능?", "맞음?",
    "버그인가", "왜 안", "어디서", "몇렙", "몇 레벨", "어케",
]

SUGGESTION_KEYWORDS = [
    "해줘", "해주세요", "해줬으면", "해주면", "추가해", "추가해주세요",
    "개선", "개편", "바꿔", "수정해", "필요", "있었으면", "있으면 좋겠다",
    "만들어줘", "줘야", "늘려줘", "줄여줘", "지원해줘",
]

POSITIVE_KEYWORDS = [
    "좋다", "좋네", "좋아요", "좋음", "재밌다", "재미있다", "꿀잼", "만족",
    "잘했다", "잘했네", "괜찮다", "혜자", "편하다", "마음에 든다",
    "갓", "최고", "추천", "호감", "잘 만든",
]

NEGATIVE_KEYWORDS = [
    "별로", "불편", "짜증", "망", "망했다", "어렵다", "너무 어렵", "문제",
    "실망", "최악", "이상하다", "이상함", "버그", "안됨", "안 된다",
    "렉", "끊김", "답답", "불만", "구리다", "구림",
]


def normalize_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def is_short_or_low_value_message(text: str) -> bool:
    t = normalize_text(text)
    c = compact_text(text)

    if not t:
        return True

    if t in SKIP_EXACT:
        return True

    if len(t) <= 2 or len(c) <= 3:
        return True

    for pattern in SKIP_PATTERNS:
        if re.match(pattern, t):
            return True

    return False


def is_question_message(text: str) -> bool:
    t = normalize_text(text)
    for q in QUESTION_HINTS:
        if q in t:
            return True
    return False


def contains_any(text: str, keywords: List[str]) -> bool:
    t = normalize_text(text)
    return any(k in t for k in keywords)


def rule_based_precheck(text: str) -> Optional[Dict[str, Any]]:
    """
    AI 호출 전에 무조건 걸러야 할 메시지 처리.
    반환값이 있으면 그 결과를 그대로 사용.
    """
    t = normalize_text(text)

    if is_short_or_low_value_message(t):
        return {
            "category": "ignore",
            "confidence": 0.99,
            "reason": "짧은 반응/잡담/의미 낮은 메시지"
        }

    if is_question_message(t):
        # 질문은 원칙적으로 ignore
        return {
            "category": "ignore",
            "confidence": 0.98,
            "reason": "질문 또는 정보 요청성 메시지"
        }

    return None


def build_prompt(message: str) -> str:
    return f"""
다음 유저 메시지를 반드시 아래 5개 중 하나로만 분류하라.

카테고리 정의:
- positive: 게임/업데이트/운영 등에 대한 명확한 칭찬, 만족, 긍정 평가
- negative: 게임/업데이트/운영 등에 대한 명확한 불만, 문제 제기, 불편, 비판
- suggestion: 개선 요청, 추가 요구, 바라는 점, 변경 요청
- trend: 유저들이 반복적으로 언급하는 이슈/관심사/화제에 해당하는 내용
- ignore: 잡담, 질문, 단순 반응, 의미 없는 채팅, 문맥 부족, 분류 가치 낮은 내용

반드시 지킬 규칙:
1. 질문은 무조건 ignore
2. 짧거나 맥락 없는 문장은 ignore
3. 감정이 명확하지 않으면 ignore
4. 단순 정보 전달은 기본적으로 ignore
5. trend는 개인 잡담이 아니라 실제 이슈/화제성이 있을 때만 선택
6. suggestion은 실제 요청/개선의도가 명확할 때만 선택
7. 절대 억지로 분류하지 마라
8. 애매하면 무조건 ignore

추가 판단 기준:
- "어떻게 함?", "~임?", "왜 안됨?" 같은 질문형은 ignore
- "ㅋㅋ", "헐", "오", "굿" 같은 단순 반응은 ignore
- 긍정/부정은 명시적 표현이 있을 때만 선택
- confidence는 0.00~1.00 사이 실수로 반환

출력은 반드시 JSON 한 줄만:
{{"category":"ignore","confidence":0.95,"reason":"짧은 질문"}}

유저 메시지:
{message}
""".strip()


def _safe_json_loads(text: str) -> Dict[str, Any]:
    text = text.strip()

    # 코드블록 제거
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


def _post_validate(message: str, result: Dict[str, Any]) -> Dict[str, Any]:
    category = str(result.get("category", "ignore")).strip().lower()
    confidence = result.get("confidence", 0.0)
    reason = str(result.get("reason", "")).strip()

    allowed = {"positive", "negative", "suggestion", "trend", "ignore"}
    if category not in allowed:
        category = "ignore"

    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0

    if confidence < 0:
        confidence = 0.0
    if confidence > 1:
        confidence = 1.0

    t = normalize_text(message)

    # 질문이면 무조건 ignore
    if is_question_message(t):
        return {
            "category": "ignore",
            "confidence": max(confidence, 0.95),
            "reason": "질문형 메시지"
        }

    # 짧은 반응이면 무조건 ignore
    if is_short_or_low_value_message(t):
        return {
            "category": "ignore",
            "confidence": max(confidence, 0.98),
            "reason": "짧은 반응/잡담"
        }

    # suggestion 과잉 방지
    if category == "suggestion" and not contains_any(t, SUGGESTION_KEYWORDS):
        return {
            "category": "ignore",
            "confidence": 0.90,
            "reason": "건의 의도가 명확하지 않음"
        }

    # positive 과잉 방지
    if category == "positive" and not contains_any(t, POSITIVE_KEYWORDS):
        if confidence < 0.90:
            return {
                "category": "ignore",
                "confidence": 0.88,
                "reason": "명시적 긍정 표현 부족"
            }

    # negative 과잉 방지
    if category == "negative" and not contains_any(t, NEGATIVE_KEYWORDS):
        if confidence < 0.90:
            return {
                "category": "ignore",
                "confidence": 0.88,
                "reason": "명시적 부정 표현 부족"
            }

    # confidence 낮으면 ignore
    if category != "ignore" and confidence < AI_MIN_CONFIDENCE:
        return {
            "category": "ignore",
            "confidence": confidence,
            "reason": f"confidence 부족({confidence:.2f})"
        }

    return {
        "category": category,
        "confidence": confidence,
        "reason": reason or "AI 분류"
    }


def review_message_with_ai(message: str) -> Dict[str, Any]:
    if not AI_REVIEW_ENABLED:
        return {
            "category": "ignore",
            "confidence": 0.0,
            "reason": "AI_REVIEW_ENABLED=false"
        }

    message = normalize_text(message)

    prechecked = rule_based_precheck(message)
    if prechecked is not None:
        return prechecked

    prompt = build_prompt(message)

    last_error = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": "너는 게임 페어리테일퀘스트 커뮤니티 메시지 분류기다."},
                    {"role": "user", "content": prompt},
                ],
            )

            raw = response.choices[0].message.content or ""
            parsed = _safe_json_loads(raw)
            return _post_validate(message, parsed)

        except Exception as e:
            last_error = e
            if attempt < AI_MAX_RETRIES:
                time.sleep(AI_RETRY_SLEEP_SEC)

    return {
        "category": "ignore",
        "confidence": 0.0,
        "reason": f"AI 오류: {last_error}"
    }
