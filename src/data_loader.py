"""샘플 CSV 및 mock 데이터 로딩."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

# 프리셋 경로 (Streamlit에서 선택)
DEFAULT_CANDIDATE_VIDEOS_CSV = DATA_DIR / "sample_candidate_videos.csv"
DEFAULT_DAILY_METRICS_CSV = DATA_DIR / "sample_daily_metrics.csv"
CREATOR_T_CANDIDATE_VIDEOS_CSV = DATA_DIR / "sample_case_creator_t_candidate_videos.csv"
CREATOR_T_DAILY_METRICS_CSV = DATA_DIR / "sample_case_creator_t_daily_metrics.csv"
SAMPLE_CHANNEL_ANALYTICS_MANUAL_CSV = DATA_DIR / "sample_channel_analytics_manual.csv"
SAMPLE_CREATOR_PROFILES_CSV = DATA_DIR / "sample_creator_profiles.csv"


def _ensure_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        return df
    out = df.copy()
    try:
        out[col] = pd.to_datetime(out[col], errors="coerce")
    except Exception as e:
        logger.warning("Could not parse datetime column %s: %s", col, e)
    return out


def load_candidate_videos(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or DATA_DIR / "sample_candidate_videos.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing sample file: {csv_path}")
    df = pd.read_csv(csv_path)
    df = _ensure_datetime(df, "published_at")
    return df


def load_daily_metrics(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or DATA_DIR / "sample_daily_metrics.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing sample file: {csv_path}")
    df = pd.read_csv(csv_path)
    df = _ensure_datetime(df, "date")
    return df


def filter_metrics_by_dates(
    df: pd.DataFrame,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df
    out = df.dropna(subset=["date"]).copy()
    if start is not None:
        out = out[out["date"] >= start]
    if end is not None:
        out = out[out["date"] <= end]
    return out.sort_values("date").reset_index(drop=True)


def filter_videos_by_dates(
    df: pd.DataFrame,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
) -> pd.DataFrame:
    if df.empty or "published_at" not in df.columns:
        return df
    out = df.dropna(subset=["published_at"]).copy()
    if start is not None:
        out = out[out["published_at"].dt.normalize() >= start.normalize()]
    if end is not None:
        end_norm = pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
        out = out[out["published_at"] < end_norm]
    return out.reset_index(drop=True)
