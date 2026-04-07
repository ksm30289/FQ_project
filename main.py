import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple
from your_filter_file import should_keep_for_trend

from config import (
    AI_REVIEW_ENABLED,
    AI_REVIEW_PARALLEL_ENABLED,
    AI_REVIEW_WORKERS,
    DEBUG_LOG,
    FILE_DEDUP_MODE,
    MAX_FILES_PER_RUN,
    ROW_DEDUP_ENABLED,
)
from drive_client import GoogleDriveClient
from parser import parse_chat_text
from sheets import GoogleSheetClient
from utils import make_file_key, make_row_hash


def log_debug(message: str) -> None:
    if DEBUG_LOG:
        print(message)


def _safe_import(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception as e:
        log_debug(f"[WARN] 모듈 import 실패: {module_name} / {e}")
        return None


def _call_first_available(obj: Any, method_names: List[str], *args, **kwargs):
    last_error = None
    for name in method_names:
        method = getattr(obj, name, None)
        if not callable(method):
            continue
        try:
            return method(*args, **kwargs)
        except TypeError as e:
            last_error = e
            continue
    if last_error:
        raise last_error
    raise AttributeError(
        f"{obj.__class__.__name__} 에서 호출 가능한 메서드를 찾지 못했습니다. "
        f"시도한 이름들: {method_names}"
    )


# =========================================================
# Drive wrappers
# =========================================================
def _list_drive_files(drive_client: GoogleDriveClient, limit: int) -> List[Dict[str, Any]]:
    return _call_first_available(
        drive_client,
        ["list_txt_files", "list_text_files", "list_files"],
        limit=limit,
    )


def _read_drive_file_text(drive_client: GoogleDriveClient, file_meta: Dict[str, Any]) -> str:
    file_id = file_meta.get("id")
    mime_type = file_meta.get("mimeType", "")

    method_names = [
        "read_text_file",
        "download_text_file",
        "download_txt_file",
        "get_file_text",
        "read_file_text",
    ]

    try:
        return _call_first_available(
            drive_client,
            method_names,
            file_id=file_id,
            mime_type=mime_type,
        )
    except TypeError:
        pass

    try:
        return _call_first_available(
            drive_client,
            method_names,
            file_id=file_id,
        )
    except TypeError:
        pass

    return _call_first_available(
        drive_client,
        method_names,
        file_id,
    )


# =========================================================
# Sheets wrappers
# =========================================================
def _get_existing_row_hashes(sheet_client: GoogleSheetClient) -> Set[str]:
    try:
        result = _call_first_available(
            sheet_client,
            [
                "get_existing_row_hashes",
                "load_existing_row_hashes",
                "read_existing_row_hashes",
            ],
        )
        return set(result or [])
    except Exception as e:
        log_debug(f"[WARN] 기존 row_hash 조회 실패, 빈 집합으로 진행: {e}")
        return set()


def _get_processed_file_keys(sheet_client: GoogleSheetClient) -> Set[str]:
    try:
        result = _call_first_available(
            sheet_client,
            [
                "get_processed_file_keys",
                "load_processed_file_keys",
                "read_processed_file_keys",
            ],
        )
        return set(result or [])
    except Exception as e:
        log_debug(f"[WARN] 기존 file_key 조회 실패, 빈 집합으로 진행: {e}")
        return set()


def _save_raw_chat_rows(sheet_client: GoogleSheetClient, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    _call_first_available(
        sheet_client,
        [
            "append_raw_chat_rows",
            "save_raw_chat_rows",
            "add_raw_chat_rows",
            "insert_raw_chat_rows",
        ],
        rows,
    )


def _save_processed_files(sheet_client: GoogleSheetClient, file_records: List[Dict[str, Any]]) -> None:
    if not file_records:
        return
    _call_first_available(
        sheet_client,
        [
            "append_processed_files",
            "save_processed_files",
            "save_file_dedup_rows",
            "append_file_dedup_rows",
        ],
        file_records,
    )


def _save_negative_rows(sheet_client: GoogleSheetClient, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    _call_first_available(
        sheet_client,
        [
            "append_negative_trend_rows",
            "save_negative_trend_rows",
            "save_negative_rows",
        ],
        rows,
    )


def _save_positive_rows(sheet_client: GoogleSheetClient, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    _call_first_available(
        sheet_client,
        [
            "append_positive_trend_rows",
            "save_positive_trend_rows",
            "save_positive_rows",
        ],
        rows,
    )


def _save_suggestion_rows(sheet_client: GoogleSheetClient, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    _call_first_available(
        sheet_client,
        [
            "append_suggestion_rows",
            "save_suggestion_rows",
            "save_suggestions_rows",
        ],
        rows,
    )


def _save_trend_rows(sheet_client: GoogleSheetClient, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    _call_first_available(
        sheet_client,
        [
            "append_trend_rows",
            "save_trend_rows",
            "save_discord_trend_rows",
        ],
        rows,
    )


# =========================================================
# Classifier helpers
# =========================================================
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


def _keyword_classify_message(message: str) -> Tuple[Optional[str], float, str]:
    text = (message or "").strip().lower()

    suggestion_keywords = [
        "해줬으면",
        "해주세요",
        "추가해",
        "추가해줘",
        "추가해줬으면",
        "개선",
        "수정해",
        "수정해주세요",
        "상향",
        "하향",
        "너프",
        "버프",
        "필요",
        "바꿔",
        "바꿔줘",
        "원함",
        "좋겠어요",
        "좋겠다",
        "부탁",
        "있으면 좋겠",
    ]
    negative_keywords = [
        "버그",
        "렉",
        "튕김",
        "최적화",
        "망겜",
        "개같",
        "다신안",
        "다신 안",
        "노잼",
        "불편",
        "짜증",
        "문제",
        "오류",
        "안됨",
        "안 돼",
        "못하겠",
        "최악",
        "개많네",
    ]
    positive_keywords = [
        "재밌",
        "꿀잼",
        "좋아요",
        "좋다",
        "최고",
        "갓겜",
        "만족",
        "잘했다",
        "잘했",
        "훌륭",
        "재미있",
        "맘에 든",
    ]

    if any(k in text for k in suggestion_keywords):
        return "suggestion", 0.72, "keyword_rule"
    if any(k in text for k in negative_keywords):
        return "negative", 0.72, "keyword_rule"
    if any(k in text for k in positive_keywords):
        return "positive", 0.72, "keyword_rule"

    return None, 0.0, "unclassified"


def _classify_with_trend_module(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mod = _safe_import("trend_classifier")
    if mod is None:
        return None

    candidates = [
        "classify_row",
        "classify_message",
        "classify_chat_row",
        "classify_trend",
    ]

    for fn_name in candidates:
        fn = getattr(mod, fn_name, None)
        if not callable(fn):
            continue

        try:
            result = fn(row)
        except TypeError:
            try:
                result = fn(row.get("message", ""))
            except Exception as e:
                log_debug(f"[WARN] trend_classifier.{fn_name} 호출 실패: {e}")
                continue
        except Exception as e:
            log_debug(f"[WARN] trend_classifier.{fn_name} 호출 실패: {e}")
            continue

        if isinstance(result, dict):
            category = _normalize_category(result.get("category"))
            if category:
                return {
                    "category": category,
                    "confidence": float(result.get("confidence", 0.7)),
                    "reason": str(result.get("reason", fn_name)),
                }

        elif isinstance(result, str):
            category = _normalize_category(result)
            if category:
                return {
                    "category": category,
                    "confidence": 0.7,
                    "reason": fn_name,
                }

        elif isinstance(result, tuple) and len(result) >= 1:
            category = _normalize_category(result[0])
            confidence = float(result[1]) if len(result) >= 2 else 0.7
            reason = str(result[2]) if len(result) >= 3 else fn_name
            if category:
                return {
                    "category": category,
                    "confidence": confidence,
                    "reason": reason,
                }

    return None


def _classify_row_base(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    result = _classify_with_trend_module(row)
    if result:
        return result

    category, confidence, reason = _keyword_classify_message(row.get("message", ""))
    if not category:
        return None

    return {
        "category": category,
        "confidence": confidence,
        "reason": reason,
    }


def _build_trend_row(raw_row: Dict[str, Any], category: str, confidence: float, reason: str) -> Dict[str, Any]:
    return {
        "date": raw_row.get("date", ""),
        "time": raw_row.get("time", ""),
        "user": raw_row.get("user", ""),
        "message": raw_row.get("message", ""),
        "source_file_name": raw_row.get("source_file_name", ""),
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "row_hash": raw_row.get("row_hash", ""),
    }


def _review_single_row_with_ai(row: Dict[str, Any]) -> Dict[str, Any]:
    mod = _safe_import("ai_reviewer")
    if mod is None:
        return row

    single_candidates = [
        "review_row_with_ai",
        "review_single_row_with_ai",
        "review_message_with_ai",
        "review_row",
        "review_one",
        "classify_row_with_ai",
    ]

    for fn_name in single_candidates:
        fn = getattr(mod, fn_name, None)
        if not callable(fn):
            continue
        try:
            reviewed = fn(row)
            if isinstance(reviewed, dict):
                reviewed_row = {
                    "date": reviewed.get("date", row.get("date", "")),
                    "time": reviewed.get("time", row.get("time", "")),
                    "user": reviewed.get("user", row.get("user", "")),
                    "message": reviewed.get("message", row.get("message", "")),
                    "source_file_name": reviewed.get("source_file_name", row.get("source_file_name", "")),
                    "category": _normalize_category(reviewed.get("category")) or row.get("category"),
                    "confidence": float(reviewed.get("confidence", row.get("confidence", 0.7))),
                    "reason": str(reviewed.get("reason", row.get("reason", ""))),
                    "row_hash": reviewed.get("row_hash", row.get("row_hash", "")),
                }
                if reviewed_row["category"]:
                    return reviewed_row
        except Exception as e:
            log_debug(f"[WARN] ai_reviewer.{fn_name} 호출 실패: {e}")

    return row


def _review_rows_with_ai(base_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not AI_REVIEW_ENABLED or not base_rows:
        return base_rows

    mod = _safe_import("ai_reviewer")
    if mod is None:
        log_debug("[WARN] ai_reviewer 모듈이 없어 기본 분류 결과로 진행")
        return base_rows

    batch_candidates = [
        "review_rows_with_ai",
        "review_batch_with_ai",
        "review_messages_with_ai",
        "review_rows",
        "review_batch",
    ]

    for fn_name in batch_candidates:
        fn = getattr(mod, fn_name, None)
        if not callable(fn):
            continue
        try:
            reviewed = fn(base_rows)
            if isinstance(reviewed, list):
                return reviewed
        except Exception as e:
            log_debug(f"[WARN] ai_reviewer.{fn_name} 호출 실패: {e}")

    if AI_REVIEW_PARALLEL_ENABLED and AI_REVIEW_WORKERS > 1:
        reviewed_rows: List[Optional[Dict[str, Any]]] = [None] * len(base_rows)
        with ThreadPoolExecutor(max_workers=AI_REVIEW_WORKERS) as executor:
            future_map = {
                executor.submit(_review_single_row_with_ai, row): idx
                for idx, row in enumerate(base_rows)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    reviewed_rows[idx] = future.result()
                except Exception as e:
                    log_debug(f"[WARN] 병렬 AI 리뷰 실패 idx={idx}: {e}")
                    reviewed_rows[idx] = base_rows[idx]
        return [row for row in reviewed_rows if row is not None]

    return [_review_single_row_with_ai(row) for row in base_rows]


def _normalize_final_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        category = _normalize_category(row.get("category"))
        if not category:
            continue
        normalized.append(
            {
                "date": row.get("date", ""),
                "time": row.get("time", ""),
                "user": row.get("user", ""),
                "message": row.get("message", ""),
                "source_file_name": row.get("source_file_name", ""),
                "category": category,
                "confidence": float(row.get("confidence", 0.7)),
                "reason": str(row.get("reason", "")),
                "row_hash": row.get("row_hash", ""),
            }
        )
    return normalized


# =========================================================
# Main
# =========================================================
def main() -> None:
    print("=== 작업 시작 ===")

    drive_client = GoogleDriveClient()
    sheet_client = GoogleSheetClient()

    if ROW_DEDUP_ENABLED:
        print("[STEP] 기존 row_hash 조회 시작")
        existing_row_hashes = _get_existing_row_hashes(sheet_client)
        log_debug(f"[DEBUG] 기존 row_hash 수: {len(existing_row_hashes)}")
    else:
        existing_row_hashes = set()
        print("[STEP] row 중복 제거 비활성화 상태")

    print("[STEP] 처리 완료 파일키 조회 시작")
    processed_file_keys = _get_processed_file_keys(sheet_client)
    log_debug(f"[DEBUG] 처리 완료 파일키 수: {len(processed_file_keys)}")

    print("[STEP] Drive 파일 조회 시작")
    files = _list_drive_files(drive_client, limit=MAX_FILES_PER_RUN)

    print(f"[INFO] Drive 조회 파일 수: {len(files)}")
    if not files:
        print("처리할 txt 파일이 없습니다.")
        print("=== 작업 종료 ===")
        return

    total_seen_files = 0
    total_processed_files = 0
    total_parsed_rows = 0
    total_raw_saved = 0
    total_classified = 0
    total_ignored = 0

    run_seen_row_hashes: Set[str] = set()

    for file_meta in files:
        total_seen_files += 1

        file_name = str(file_meta.get("name", "")).strip()
        file_id = str(file_meta.get("id", "")).strip()
        file_key = make_file_key(file_meta, mode=FILE_DEDUP_MODE)

        if file_key in processed_file_keys:
            print(f"[SKIP] 이미 처리된 파일: {file_name}")
            continue

        print(f"[FILE] 처리 시작: {file_name}")

        # 1) 읽기
        try:
            text = _read_drive_file_text(drive_client, file_meta)
        except Exception as e:
            print(f"[ERROR] 파일 읽기 실패: {file_name} / {e}")
            continue

        # 2) 파싱
        try:
            parsed_rows = parse_chat_text(text, source_file_name=file_name)
            print(f"파싱 행 수: {len(parsed_rows)}")
        except Exception as e:
            print(f"[ERROR] 파일 파싱 실패: {file_name} / {e}")
            continue

        # 3) row_hash 부여 + dedup
        new_rows: List[Dict[str, Any]] = []
        for row in parsed_rows:
            row_hash = make_row_hash(
                row.get("date", ""),
                row.get("time", ""),
                row.get("user", ""),
                row.get("message", ""),
                row.get("source_file_name", ""),
            )
            row["row_hash"] = row_hash

            if ROW_DEDUP_ENABLED:
                if row_hash in existing_row_hashes or row_hash in run_seen_row_hashes:
                    total_ignored += 1
                    continue

            new_rows.append(row)
            existing_row_hashes.add(row_hash)
            run_seen_row_hashes.add(row_hash)

        total_parsed_rows += len(new_rows)

        # 4) raw_chat 즉시 저장
        if new_rows:
            try:
                print("[STEP] raw_chat 저장 시작")
                _save_raw_chat_rows(sheet_client, new_rows)
                total_raw_saved += len(new_rows)
                print(f"[INFO] raw_chat 저장 완료: {len(new_rows)}건")
            except Exception as e:
                print(f"[ERROR] raw_chat 저장 실패: {file_name} / {e}")
                continue
        else:
            print("[INFO] raw_chat 저장할 데이터 없음")

        # 5) 1차 분류
        print("[STEP] AI 분류 대상 수집 시작")

        base_classified_rows = []

        for row in new_rows:

            # ✅ 여기 추가 (핵심 필터)
            if not should_keep_for_trend(row):
                total_ignored += 1
                continue

            classified = _classify_row_base(row)
            if not classified:
                continue

            trend_row = _build_trend_row(
                raw_row=row,
                category=classified["category"],
                confidence=classified["confidence"],
                reason=classified["reason"],
            )
            base_classified_rows.append(trend_row)

        print(f"[STEP] AI 분류 대상 수집 완료: {len(base_classified_rows)}건")

        # 6) AI 리뷰
        if base_classified_rows:
            print(
                "[STEP] 병렬 AI 분류 시작"
                if AI_REVIEW_ENABLED and AI_REVIEW_PARALLEL_ENABLED and AI_REVIEW_WORKERS > 1
                else "[STEP] 순차 AI 분류 시작"
            )
        else:
            print("[STEP] AI 분류 건너뜀")

        try:
            final_classified_rows = _review_rows_with_ai(base_classified_rows)
            normalized_final_rows = _normalize_final_rows(final_classified_rows)
        except Exception as e:
            print(f"[ERROR] AI 분류 실패: {file_name} / {e}")
            normalized_final_rows = base_classified_rows

        negative_rows = [row for row in normalized_final_rows if row["category"] == "negative"]
        positive_rows = [row for row in normalized_final_rows if row["category"] == "positive"]
        suggestion_rows = [row for row in normalized_final_rows if row["category"] == "suggestion"]

        # 7) 분류 시트 즉시 저장
        print("[STEP] 분류 시트 저장 시작")
        try:
            if negative_rows:
                _save_negative_rows(sheet_client, negative_rows)
                print(f"[INFO] 부정 동향 저장 완료: {len(negative_rows)}건")
            else:
                print("[INFO] 부정 동향 저장할 데이터 없음")

            if positive_rows:
                _save_positive_rows(sheet_client, positive_rows)
                print(f"[INFO] 긍정 동향 저장 완료: {len(positive_rows)}건")
            else:
                print("[INFO] 긍정 동향 저장할 데이터 없음")

            if suggestion_rows:
                _save_suggestion_rows(sheet_client, suggestion_rows)
                print(f"[INFO] 건의 저장 완료: {len(suggestion_rows)}건")
            else:
                print("[INFO] 건의 저장할 데이터 없음")

            if normalized_final_rows:
                _save_trend_rows(sheet_client, normalized_final_rows)
                print(f"[INFO] 디스코드 동향 저장 완료: {len(normalized_final_rows)}건")
            else:
                print("[INFO] 디스코드 동향 저장할 데이터 없음")
        except Exception as e:
            print(f"[ERROR] 분류 시트 저장 실패: {file_name} / {e}")

        # 8) file_dedup 즉시 저장
        try:
            print("[STEP] 파일 dedup 기록 저장 시작")
            _save_processed_files(
                sheet_client,
                [
                    {
                        "file_id": file_id,
                        "file_name": file_name,
                        "file_key": file_key,
                    }
                ],
            )
            processed_file_keys.add(file_key)
            total_processed_files += 1
            print("[INFO] 처리 파일 기록 저장 완료: 1건")
        except Exception as e:
            print(f"[ERROR] 파일 dedup 기록 저장 실패: {file_name} / {e}")

        total_classified += len(normalized_final_rows)

    print("=== 작업 완료 ===")
    print(f"처리 파일 수: {total_processed_files}")
    print(f"파싱 행 수: {total_parsed_rows}")
    print(f"raw_chat 저장 수: {total_raw_saved}")
    print(f"분류 저장 수: {total_classified}")
    print(f"ignore 수: {total_ignored}")


if __name__ == "__main__":
    main()
