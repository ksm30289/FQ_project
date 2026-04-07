from typing import Dict, List

from config import AI_REVIEW_BATCH_SIZE
from ai_reviewer import classify_message_batch


def _chunked(items: List[Dict], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _to_trend_row(raw_row: Dict, reason: str):
    return [
        raw_row.get("datetime", ""),
        raw_row.get("user", ""),
        raw_row.get("message", ""),
        raw_row.get("source_file", ""),
        reason,
        raw_row.get("row_hash", ""),
    ]


def classify_and_write_trends(sheet_client, rows: List[Dict]) -> int:
    if not rows:
        print("[CLASSIFIER] 입력 rows 없음")
        return 0

    batch_size = max(1, AI_REVIEW_BATCH_SIZE)
    print(f"[CLASSIFIER] 분류 시작: 총 {len(rows)}건 / batch_size={batch_size}")

    negative_rows = []
    positive_rows = []
    suggestion_rows = []

    total_processed = 0

    for batch_index, batch_rows in enumerate(_chunked(rows, batch_size), start=1):
        print(f"[CLASSIFIER] 배치 처리 시작: {batch_index} / {len(batch_rows)}건")
        results = classify_message_batch(batch_rows)

        for raw_row, result in zip(batch_rows, results):
            category = result.get("category", "ignore")
            reason = result.get("reason", "")

            if category == "negative":
                negative_rows.append(_to_trend_row(raw_row, reason))
            elif category == "positive":
                positive_rows.append(_to_trend_row(raw_row, reason))
            elif category == "suggestion":
                suggestion_rows.append(_to_trend_row(raw_row, reason))

        total_processed += len(batch_rows)

    written = 0

    if negative_rows:
        sheet_client.append_negative_rows(negative_rows)
        print(f"[CLASSIFIER] negative 저장: {len(negative_rows)}건")
        written += len(negative_rows)

    if positive_rows:
        sheet_client.append_positive_rows(positive_rows)
        print(f"[CLASSIFIER] positive 저장: {len(positive_rows)}건")
        written += len(positive_rows)

    if suggestion_rows:
        sheet_client.append_suggestion_rows(suggestion_rows)
        print(f"[CLASSIFIER] suggestion 저장: {len(suggestion_rows)}건")
        written += len(suggestion_rows)

    print(f"[CLASSIFIER] 배치 처리 완료: {total_processed}건")
    print(f"[CLASSIFIER] 최종 저장 건수: {written}건")
    return written
