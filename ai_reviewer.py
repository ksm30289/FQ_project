from openai import OpenAI
from config import OPENAI_API_KEY, AI_REVIEW_MODEL, AI_REVIEW_BATCH_SIZE

client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """
너는 게임 '페어리테일 퀘스트'의 커뮤니티 분석 AI다.

아래 메시지를 분석해서 다음 중 하나로 분류해라:

1. positive (긍정)
2. negative (불만/비판)
3. suggestion (건의/개선요청)
4. noise (잡담/무의미/맥락없는 대화)

규칙:
- 게임 관련 없는 대화는 noise
- 짧은 감탄, 욕설 단독은 noise
- 개선 요청은 suggestion
- 칭찬/만족은 positive
- 불만/버그/비판은 negative

출력은 JSON 배열로만:
[
  {"category": "..."}
]
"""


def chunk_list(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def classify_batch(messages: list):
    """
    messages: ["텍스트1", "텍스트2", ...]
    """
    if not messages:
        return []

    prompt = "메시지 목록:\n"
    for i, m in enumerate(messages):
        prompt += f"{i+1}. {m}\n"

    try:
        response = client.chat.completions.create(
            model=AI_REVIEW_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content

        import json
        result = json.loads(content)

        return [r["category"] for r in result]

    except Exception as e:
        print(f"[AI ERROR] {e}")
        return ["noise"] * len(messages)


def classify_messages(rows: list):
    """
    rows:
    [
        {"datetime":..., "user":..., "message":...}
    ]
    """
    results = []

    for chunk in chunk_list(rows, AI_REVIEW_BATCH_SIZE):
        messages = [r["message"] for r in chunk]
        categories = classify_batch(messages)

        for r, c in zip(chunk, categories):
            r["category"] = c
            results.append(r)

    return results
