"""sample_creator_profiles.csv → CreatorProfile."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.creator_profile import CreatorProfile, MonetizationProfile

logger = logging.getLogger(__name__)


def _bool_cell(x: object) -> bool:
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in ("1", "true", "yes", "y")


def row_to_creator_profile(row: pd.Series) -> CreatorProfile:
    monet = MonetizationProfile(
        longform_share=float(row.get("longform_share", 0.4) or 0.4),
        shorts_share=float(row.get("shorts_share", 0.1) or 0.1),
        sponsorship_share=float(row.get("sponsorship_share", 0.25) or 0.25),
        donation_membership_share=float(row.get("donation_membership_share", 0.15) or 0.15),
        live_share=float(row.get("live_share", 0.05) or 0.05),
        external_share=float(row.get("external_share", 0.05) or 0.05),
    )
    sub_raw = pd.to_numeric(row.get("subscriber_count"), errors="coerce")
    subscriber_count = None if pd.isna(sub_raw) else int(sub_raw)

    return CreatorProfile(
        creator_name=str(row.get("creator_name", "unknown")).strip() or "unknown",
        subscriber_count=subscriber_count,
        avg_daily_views=float(pd.to_numeric(row.get("avg_daily_views"), errors="coerce"))
        if pd.notna(pd.to_numeric(row.get("avg_daily_views"), errors="coerce"))
        else None,
        avg_daily_comments=float(pd.to_numeric(row.get("avg_daily_comments"), errors="coerce"))
        if pd.notna(pd.to_numeric(row.get("avg_daily_comments"), errors="coerce"))
        else None,
        content_category=str(row.get("content_category", "general") or "general"),
        monetization=monet,
        platform_concentration_score=float(
            pd.to_numeric(row.get("platform_concentration_score"), errors="coerce") or 0.5
        ),
        content_sensitivity_score=float(
            pd.to_numeric(row.get("content_sensitivity_score"), errors="coerce") or 0.5
        ),
        face_voice_exposure_score=float(
            pd.to_numeric(row.get("face_voice_exposure_score"), errors="coerce") or 0.5
        ),
        fan_community_dependency_score=float(
            pd.to_numeric(row.get("fan_community_dependency_score"), errors="coerce") or 0.5
        ),
        past_attack_history_score=float(
            pd.to_numeric(row.get("past_attack_history_score"), errors="coerce") or 0.3
        ),
        response_capacity_score=float(pd.to_numeric(row.get("response_capacity_score"), errors="coerce") or 0.5),
        mcn_affiliated=_bool_cell(row.get("mcn_affiliated", False)),
        has_legal_pr_support=_bool_cell(row.get("has_legal_pr_support", False)),
    )


def load_creator_profile_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing creator profiles CSV: {path}")
    return pd.read_csv(path)


def resolve_profile_from_csv(csv_path: Path, creator_display_name: str) -> CreatorProfile | None:
    """creator_name 컬럼이 정확히 일치하는 행만 로드."""
    df = load_creator_profile_csv(csv_path)
    if "creator_name" not in df.columns:
        logger.warning("CSV has no creator_name column")
        return None
    name = creator_display_name.strip()
    mask = df["creator_name"].astype(str).str.strip() == name
    hits = df[mask]
    if hits.empty:
        return None
    return row_to_creator_profile(hits.iloc[0])


def default_creator_profile(creator_display_name: str) -> CreatorProfile:
    """CSV에 없을 때 최소 프로필(가중치·배수 = 기본)."""
    return CreatorProfile(creator_name=creator_display_name.strip() or "unknown")
