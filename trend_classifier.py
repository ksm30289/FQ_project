from typing import Dict, Optional


CATEGORY_TO_SHEET = {
    "positive": "긍정 동향",
    "negative": "부정 동향",
    "suggestion": "건의",
    "trend": "일반 동향",
}


def classify_row_with_ai_result(ai_result: Dict) -> Optional[str]:
    """
    ai_result 예:
    {
        "category": "negative",
        "confidence": 0.91,
        "reason": "명시적 불만"
    }

    반환:
    - "긍정 동향"
    - "부정 동향"
    - "건의"
    - "일반 동향"
    - None (ignore)
    """
    category = str(ai_result.get("category", "ignore")).strip().lower()
    return CATEGORY_TO_SHEET.get(category)
