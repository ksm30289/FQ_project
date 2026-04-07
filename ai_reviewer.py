import os
import json
from openai import OpenAI


SYSTEM_PROMPT = """
너는 게임 "페어리테일 퀘스트" 커뮤니티 대화 분류기다.
각 메시지를 아래 4개 중 하나로 분류한다.

- negative: 불만, 비판, 욕설, 부정적 평가, 문제 제기
- positive: 칭찬, 만족, 긍정 반응
- suggestion: 개선 제안, 아이디어, 요청, 건의
- ignore: 잡담, 의미 없는 대화, 분류 가치 낮음

반드시 JSON 배열로만 답변해라.
각 원소는 아래 형식:
{
  "category": "negative|positive|suggestion|ignore",
  "reason": "짧은 판단 이유"
}
"""


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 비어 있습니다.")
    return OpenAI(api_key=api_key)


def classify_message_batch(rows):
    if not rows:
        return []

    client = get_openai_client()

    payload = []
    for idx, row in enumerate(rows, start=1):
        payload.append({
            "index": idx,
            "user": row.get("user", ""),
            "message": row.get("message", ""),
        })

    user_prompt = f"""
다음 메시지들을 분류해라.
반드시 JSON 배열만 출력해라.

입력:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""

    print(f"[AI] 분류 요청 시작: {len(rows)}건")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content.strip()
    print(f"[AI] 원본 응답: {content[:500]}")

    try:
        result = json.loads(content)
    except Exception as e:
        raise ValueError(f"AI 응답 JSON 파싱 실패: {e} / content={content}")

    if not isinstance(result, list):
        raise ValueError("AI 응답이 리스트(JSON 배열)가 아닙니다.")

    if len(result) != len(rows):
        raise ValueError(
            f"AI 응답 개수 불일치: 입력={len(rows)}, 응답={len(result)}"
        )

    return result
