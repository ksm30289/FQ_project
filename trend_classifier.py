from ai_reviewer import classify_message_batch


def classify_and_write_trends(sheet_client, rows):
    """
    rows: raw_chat에 저장된 row dict 리스트
    반환값: 분류 시트에 실제로 저장된 총 건수
    """
    if not rows:
        print("[CLASSIFIER] 입력 rows 없음")
        return 0

    print(f"[CLASSIFIER] 분류 시작: {len(rows)}건")

    negative_rows = []
    positive_rows = []
    suggestion_rows = []

    results = classify_message_batch(rows)
    print(f"[CLASSIFIER] AI 결과 수: {len(results)}")

    for row, result in zip(rows, results):
        category = (result.get("category") or "").strip().lower()
        reason = (result.get("reason") or "").strip()

        output_row = [
            row.get("date", ""),
            row.get("time", ""),
            row.get("user", ""),
            row.get("message", ""),
            row.get("source_file", ""),
            reason,
        ]

        if category == "negative":
            negative_rows.append(output_row)
        elif category == "positive":
            positive_rows.append(output_row)
        elif category == "suggestion":
            suggestion_rows.append(output_row)

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

    print(f"[CLASSIFIER] 총 저장 건수: {written}")
    return written
