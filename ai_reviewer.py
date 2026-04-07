import json
from typing import Dict, List

from openai import OpenAI

from config import OPENAI_API_KEY, AI_REVIEW_MODEL


SYSTEM_PROMPT = """
너는 게임 "페어리테일 퀘스트"의 커뮤니티 대화 분류기다.

각 메시지를 아래 4가지 중 하나로 분류한다.

- negative:
  불만, 비판, 짜증, 욕설, 운영/밸런스/버그에 대한 부정적 반응, 실망, 문제 제기
- positive:
  칭찬, 만족, 감사, 좋은 평가, 재미있다/괜찮다/잘했다 같은 긍정 반응
- suggestion:
  개선 아이디어, 요청, 제안, 건의, ~해달라/~였으면 좋겠다 식의 의견
- ignore:
  잡담, 인사, 의미 없는 짧은 반응, 단순 대화, 분류 가치가 낮은 메시지

규칙:
1. 반드시 JSON 배열만 출력한다.
2. 배열 길이는 입력 메시지 수와 같게 맞춘다.
3. 각 원소는 반드시 아래 형식만 사용한다.
{
  "index": 1,
  "category": "negative|positive|suggestion|ignore",
  "reason": "짧은 판단 이유"
}
4. index는 입력의 index와 정확히 동일해야 한다.
5. 코드블록 마크다운은 쓰지 않는다.
6. reason은 30자 이내 한국어로 작성한다.
"""


def _get_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def _build_payload(rows: List[Dict]) -> List[Dict]:
    payload = []
    for idx, row in enumerate(rows, start=1):
        payload.append({
            "index": idx,
            "user": row.get("user", ""),
            "message": row.get("message", ""),
        })
    return payload


def _normalize_item(item: Dict, expected_index: int) -> Dict:
    if not isinstance(item, dict):
        return {
            "index": expected_index,
            "category": "ignore",
            "reason": "응답 형식 오류",
        }

    try:
        index = int(item.get("index", expected_index))
    except Exception:
        index = expected_index

    category = str(item.get("category", "ignore")).strip().lower()
    reason = str(item.get("reason", "")).strip()

    if category not in {"negative", "positive", "suggestion", "ignore"}:
        category = "ignore"

    if not reason:
        reason = "자동 보정"

    return {
        "index": index,
        "category": category,
        "reason": reason,
    }


def classify_message_batch(rows: List[Dict]) -> List[Dict]:
    if not rows:
        return []

    client = _get_client()
    payload = _build_payload(rows)

    user_prompt = (
        "다음 입력 메시지들을 분류해라.\n"
        "반드시 JSON 배열만 출력해라.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    print(f"[AI] 분류 요청 시작: {len(rows)}건 / model={AI_REVIEW_MODEL}")

    response = client.chat.completions.create(
        model=AI_REVIEW_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = (response.choices[0].message.content or "").strip()
    print(f"[AI] 응답 미리보기: {content[:500]}")

    try:
        raw_result = json.loads(content)
    except Exception as e:
        raise RuntimeError(f"AI 응답 JSON 파싱 실패: {e} / content={content}") from e

    if not isinstance(raw_result, list):
        raise RuntimeError("AI 응답이 JSON 배열이 아닙니다.")

    expected_count = len(rows)

    normalized_items = []
    for idx, item in enumerate(raw_result, start=1):
        normalized_items.append(_normalize_item(item, idx))

    # index 기준으로 재정렬 + 중복 제거
    by_index = {}
    for item in normalized_items:
        idx = item["index"]
        if 1 <= idx <= expected_count and idx not in by_index:
            by_index[idx] = item

    # 빠진 index는 ignore로 보정
    repaired = []
    for idx in range(1, expected_count + 1):
        repaired.append(
            by_index.get(
                idx,
                {
                    "index": idx,
                    "category": "ignore",
                    "reason": "응답 누락 자동보정",
                },
            )
        )

    if len(raw_result) != expected_count:
        print(
            f"[WARN] AI 응답 개수 불일치 보정: 입력={expected_count}, 응답={len(raw_result)}, 최종={len(repaired)}"
        )

    return repaired
