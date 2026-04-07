import json
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import (
    AI_MAX_RETRIES,
    AI_MIN_CONFIDENCE,
    AI_RETRY_SLEEP_SEC,
    OPENAI_MODEL,
)

client = OpenAI()


def _extract_message_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("message", "")).strip()
    return str(value or "").strip()


def _normalize_category(category: Optional[str]) -> Optional[str]:
    if not category:
        return None

    c = str(category).strip().lower()
    mapping = {
        "negative": "negative",
        "neg": "negative",
        "부정": "negative",
        "positive": "positive",
        "pos": "positive",
        "긍정": "positive",
        "suggestion": "suggestion",
        "suggestions": "suggestion",
        "proposal": "suggestion",
        "feedback": "suggestion",
        "건의": "suggestion",
        "제안": "suggestion",
        "other": None,
        "others": None,
        "잡담": None,
        "기타": None,
        "none": None,
        "unknown": None,
    }
    return mapping.get(c, None)


def _build_prompt(message: str) -> str:
    return f"""
다음 게임 페어리테일퀘스트 커뮤니티 채팅 메시지를 분류하세요.

분류 기준:
- positive: 게임/업데이트/운영 등에 대한 긍정 반응
- negative: 게임/업데이트/운영 등에 대한 부정 반응, 불만, 버그 제보
- suggestion: 개선 제안, 요청, 건의
- other: 잡담, 인사, 거래, 길드 모집, 일반 대화 등 동향성 없는 내용

반드시 JSON만 출력하세요:
{{
  "category": "positive|negative|suggestion|other",
  "confidence": 0.0,
  "reason": "짧은 이유"
}}

메시지:
{message}
""".strip()


def _call_openai_for_message(message: str) -> Dict[str, Any]:
    prompt = _build_prompt(message)
    last_error = None

    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "너는 게임 커뮤니티 메시지 분류기다. 반드시 JSON만 출력한다.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            content = (response.choices[0].message.content or "").strip()
            data = json.loads(content)

            category = _normalize_category(data.get("category"))
            confidence = float(data.get("confidence", 0.0))
            reason = str(data.get("reason", "")).strip()

            if confidence < AI_MIN_CONFIDENCE:
                category = None

            return {
                "category": category,
                "confidence": confidence,
                "reason": reason,
            }

        except Exception as e:
            last_error = e
            if attempt < AI_MAX_RETRIES:
                time.sleep(AI_RETRY_SLEEP_SEC * attempt)

    return {
        "category": None,
        "confidence": 0.0,
        "reason": f"ai_error: {last_error}",
    }


def review_message_with_ai(item: Any) -> Dict[str, Any]:
    message = _extract_message_text(item)

    if not message:
        return {
            "category": None,
            "confidence": 0.0,
            "reason": "empty_message",
        }

    return _call_openai_for_message(message)


def review_row_with_ai(row: Dict[str, Any]) -> Dict[str, Any]:
    result = review_message_with_ai(row)

    return {
        "date": row.get("date", ""),
        "time": row.get("time", ""),
        "user": row.get("user", ""),
        "message": row.get("message", ""),
        "source_file_name": row.get("source_file_name", ""),
        "category": result.get("category"),
        "confidence": result.get("confidence", 0.0),
        "reason": result.get("reason", ""),
        "row_hash": row.get("row_hash", ""),
    }


def review_rows_with_ai(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reviewed: List[Dict[str, Any]] = []
    for row in rows:
        reviewed.append(review_row_with_ai(row))
    return reviewed


def review_batch_with_ai(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return review_rows_with_ai(rows)


def review_messages_with_ai(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return review_rows_with_ai(rows)


def review_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return review_rows_with_ai(rows)


def review_batch(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return review_rows_with_ai(rows)
