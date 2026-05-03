"""빅카인즈 등 뉴스 건수 (향후 연동 스텁)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR


class BigKindsCollector:
    def __init__(self, sample_daily_csv: Path | None = None) -> None:
        self._sample_daily_csv = sample_daily_csv or (DATA_DIR / "sample_daily_metrics.csv")

    def fetch_news_count(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        # TODO: BIGKINDS_API_KEY 기반 Open API 또는 수동 CSV 전용 경로
        # 공공·빅카인즈 랩 등은 키워드별 실시간 카운트가 아닐 수 있어 MVP는 CSV 병합만 수행
        try:
            if not self._sample_daily_csv.exists():
                return pd.DataFrame(columns=["date", "news_count"])
            dm = pd.read_csv(self._sample_daily_csv)
            dm["date"] = pd.to_datetime(dm["date"], errors="coerce")
            cols = ["date", "news_count"] if "news_count" in dm.columns else ["date"]
            out = dm[cols].dropna(subset=["date"])
            if start_date is not None:
                out = out[out["date"] >= pd.Timestamp(start_date)]
            if end_date is not None:
                out = out[out["date"] <= pd.Timestamp(end_date)]
            _ = (creator_name, keywords)
            return out.sort_values("date").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=["date", "news_count"])
