#!/usr/bin/env python3
"""Naver Search API 외부 확산 수집 스모크 테스트 — 자격 증명·HTTP·파싱 실패 메시지를 구분합니다."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src.collectors.naver_search_collector import NaverSearchCollector  # noqa: E402


def main() -> int:
    env_path = ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    else:
        load_dotenv()

    col = NaverSearchCollector()
    if not col.configured():
        print("FAIL: NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 비어 있습니다(.env 또는 환경 변수).")
        return 2

    end_d = date.today()
    start_d = end_d - timedelta(days=7)
    creator = "쯔양"
    keywords = ["협박", "구제역", "해명", "렉카", "논란"]

    try:
        raw_df, daily_df, meta = col.fetch_external_amplification(
            creator,
            keywords,
            start_d,
            end_d,
            max_pages=1,
        )
    except Exception as e:
        print(f"FAIL: 파싱/실행 예외 — {type(e).__name__}: {e}")
        return 3

    st = meta.get("naver_search_status")
    print("naver_search_status:", st)
    print("queries (count):", len(meta.get("queries") or []))
    print(
        "collected news/blog/cafe:",
        meta.get("collected_news"),
        meta.get("collected_blog"),
        meta.get("collected_cafe"),
    )
    print("external_amplification_total:", meta.get("external_amplification_total"))

    if st == "error":
        print("FAIL: HTTP 또는 API 오류 —", meta.get("naver_search_error"))
        return 4
    if st == "missing_key":
        print("FAIL: 자격 불일치 분기(설정 확인).")
        return 2

    print("\n--- raw_results_df.head() ---")
    try:
        print(raw_df.head(15).to_string(index=False))
    except Exception as e:
        print("FAIL: raw DataFrame 출력 오류:", e)
        return 5

    print("\n--- daily_external_df ---")
    print(daily_df.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
