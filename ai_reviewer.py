# ai_reviewer.py
import json
from typing import Dict, List

from openai import OpenAI

from config import OPENAI_API_KEY, AI_REVIEW_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
너는 게임 커뮤니티 채팅 분류 검수기다.
아래 4개 라벨 중 하나만 선택해라.

- negative: 게임/운영/서비스에 대한 불만, 문제, 오류, 이탈 징후
- positive: 게임/운영/서비스에 대한 명확한 긍정 평가
- suggestion: 기능 추가/변경/개선 요청
- ignore: 잡담, 농담, 유저 간 사적 대화, 의미 없는 반응, 분류 가치 낮은 문장

규칙:
1. 반드시 4개 중 하나만 고른다.
2. 게임/운영/서비스와 관련 없는 대화는 ignore다.
3. 단순 감탄사, 맞장구, 잡담은 ignore다.
4. 문맥이 약하면 보수적으로 ignore를 선택한다.
5. 출력은 JSON 객체 하나만 반환한다.
"""

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {
            "type": "string",
            "enum": ["negative", "positive", "suggestion", "ignore"]
        },
        "reason": {
            "type": "string"
        }
    },
    "required": ["label", "reason"],
    "additionalProperties": False
}


def review_message_with_ai(message: str, detected_keywords: List[str]) -> Dict[str, str]:
    user_prompt = f"""
메시지:
{message}

키워드 기반 후보:
{", ".join(detected_keywords) if detected_keywords else "(없음)"}

위 메시지를 최종 분류해라.
"""

    response = client.responses.create(
        model=AI_REVIEW_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "trend_review",
                "schema": JSON_SCHEMA,
                "strict": True,
            }
        },
    )

    raw_text = response.output_text
    data = json.loads(raw_text)

    return {
        "label": data["label"],
        "reason": data["reason"].strip(),
    }
