"""공개 채널·수익 proxy 지표 — Social Blade / Vling / Playboard 향후, 현재 manual_csv."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

Provider = Literal["manual_csv", "socialblade", "vling", "playboard"]


class PublicChannelAnalyticsCollector:
    """
    provider:
      - manual_csv: 사용자가 내보낸 CSV (Vling·수동 정리 등 수익 proxy 포함 가능)
      - socialblade/vling/playboard: 자동 연동 미구현 → manual 또는 샘플 daily fallback
    """

    def __init__(
        self,
        provider: Provider = "manual_csv",
        manual_metrics_csv: Path | None = None,
        fallback_daily_csv: Path | None = None,
        disallow_csv_reads: bool = False,
    ) -> None:
        self.provider = provider
        self._manual_metrics_csv = manual_metrics_csv
        self._fallback_daily_csv = fallback_daily_csv or (DATA_DIR / "sample_daily_metrics.csv")
        self._disallow_csv_reads = bool(disallow_csv_reads)

    def fetch_public_channel_metrics(
        self,
        channel_url: str,
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        _ = channel_url

        if self._disallow_csv_reads:
            return pd.DataFrame(
                columns=[
                    "date",
                    "creator_channel_daily_views",
                    "creator_channel_subscriber_change",
                ]
            )

        if self.provider != "manual_csv":
            logger.info(
                "PublicChannelAnalyticsCollector: provider=%s 는 아직 미구현 — CSV fallback 사용",
                self.provider,
            )

        path = self._manual_metrics_csv
        if path and path.exists():
            try:
                return self._read_channel_columns(path, start_date, end_date)
            except Exception as e:
                logger.warning("manual_metrics_csv 읽기 실패: %s", e)

        try:
            if not self._fallback_daily_csv.exists():
                return pd.DataFrame(
                    columns=["date", "creator_channel_daily_views", "creator_channel_subscriber_change"]
                )
            dm = pd.read_csv(self._fallback_daily_csv)
            dm["date"] = pd.to_datetime(dm["date"], errors="coerce")
            keep = ["date"]
            if "creator_channel_daily_views" in dm.columns:
                keep.append("creator_channel_daily_views")
            if "creator_channel_subscriber_change" in dm.columns:
                keep.append("creator_channel_subscriber_change")
            out = dm[keep].dropna(subset=["date"])
            if start_date is not None:
                out = out[out["date"] >= pd.Timestamp(start_date)]
            if end_date is not None:
                out = out[out["date"] <= pd.Timestamp(end_date)]
            return out.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.warning("채널 지표 fallback 실패: %s", e)
            return pd.DataFrame(
                columns=["date", "creator_channel_daily_views", "creator_channel_subscriber_change"]
            )

    @staticmethod
    def _read_channel_columns(csv_path: Path, start_date: date | None, end_date: date | None) -> pd.DataFrame:
        dm = pd.read_csv(csv_path)
        dm["date"] = pd.to_datetime(dm["date"], errors="coerce")
        cols = ["date"]
        extras = [
            "creator_channel_daily_views",
            "creator_channel_subscriber_change",
            "estimated_daily_revenue_low",
            "estimated_daily_revenue_high",
            "rpm_proxy",
            "shorts_ratio",
            "longform_ratio",
            "source",
        ]
        for c in extras:
            if c in dm.columns:
                cols.append(c)
        out = dm[cols].dropna(subset=["date"])
        if start_date is not None:
            out = out[out["date"] >= pd.Timestamp(start_date)]
        if end_date is not None:
            out = out[out["date"] <= pd.Timestamp(end_date)]
        return out.sort_values("date").reset_index(drop=True)
