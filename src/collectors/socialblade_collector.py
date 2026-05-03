"""하위 호환: 기존 이름으로 PublicChannelAnalyticsCollector 래핑."""

from __future__ import annotations

from pathlib import Path

from src.collectors.public_channel_analytics_collector import PublicChannelAnalyticsCollector


class SocialBladeCollector(PublicChannelAnalyticsCollector):
    def __init__(self, sample_daily_csv: Path | None = None) -> None:
        super().__init__(
            provider="manual_csv",
            manual_metrics_csv=None,
            fallback_daily_csv=sample_daily_csv,
        )
