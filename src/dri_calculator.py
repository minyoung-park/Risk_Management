"""DRI 규칙 기반 계산 — 보험 자동 지급 아님, 경보/검토 트리거 (Creator Profile 보정 옵션)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.creator_profile import CreatorProfile
from src.utils import safe_z, z_to_normalized_score

logger = logging.getLogger(__name__)

_QUANT_FEATURES: tuple[tuple[str, str, float], ...] = (
    ("risk_candidate_content_spike", "candidate_video_count", 0.20),
    ("candidate_content_exposure_spike", "candidate_video_total_views", 0.15),
    ("comment_volume_spike", "candidate_video_comment_count", 0.15),
    ("search_spike", "search_index", 0.10),
    ("external_amplification", "external_amplification_count", 0.10),
)

_NLP_FEATURES: tuple[tuple[str, float], ...] = (
    ("toxicity_score", 0.10),
    ("narrative_duplication_score", 0.10),
    ("creator_targeting_context_score", 0.10),
)


@dataclass(frozen=True)
class DRIBaseline:
    mu: pd.Series
    sigma: pd.Series


def default_dri_feature_weights() -> dict[str, float]:
    d: dict[str, float] = {}
    for key, _, w in _QUANT_FEATURES:
        d[key] = float(w)
    for key, w in _NLP_FEATURES:
        d[key] = float(w)
    return d


def adjust_weights_by_creator_profile(
    base_weights: dict[str, float],
    profile: CreatorProfile | None,
) -> dict[str, float]:
    """프로필별로 합 1 유지 재정규화. profile None이면 base 복사."""
    if profile is None:
        return dict(base_weights)

    mt = profile.monetization.normalize()
    w = {k: max(0.0, float(v)) for k, v in base_weights.items()}

    w["risk_candidate_content_spike"] += 0.05 * mt.shorts_share
    w["candidate_content_exposure_spike"] += 0.05 * mt.longform_share

    w["search_spike"] += 0.04 * mt.sponsorship_share
    w["external_amplification"] += 0.04 * mt.sponsorship_share
    w["creator_targeting_context_score"] += 0.04 * mt.sponsorship_share

    fandom_share = mt.donation_membership_share + mt.live_share
    w["comment_volume_spike"] += 0.05 * fandom_share
    w["toxicity_score"] += 0.04 * fandom_share
    w["narrative_duplication_score"] += 0.04 * fandom_share

    w["creator_targeting_context_score"] += 0.04 * float(profile.content_sensitivity_score)

    total = sum(max(0.0, v) for v in w.values())
    if total <= 0:
        return dict(base_weights)
    return {k: max(0.0, v) / total for k, v in w.items()}


def resolved_weights_for_profile(profile: CreatorProfile | None) -> dict[str, float]:
    """UI/리포트용: 적용되는 DRI 피처 가중치 테이블."""
    return adjust_weights_by_creator_profile(default_dri_feature_weights(), profile)


def build_baseline(daily_metrics: pd.DataFrame) -> DRIBaseline:
    """정량 피처에 대한 평균/표준편차만 산출 (baseline 구간 행만 넣어 호출됨)."""
    cols = list({col for _, col, __ in _QUANT_FEATURES if col in daily_metrics.columns})
    mu_dict: dict[str, float] = {}
    sigma_dict: dict[str, float] = {}
    for c in cols:
        series = pd.to_numeric(daily_metrics[c], errors="coerce").dropna()
        if series.empty:
            mu_dict[c] = 0.0
            sigma_dict[c] = 0.0
            continue
        mu_dict[c] = float(series.mean())
        sd = float(series.std(ddof=0))
        if not np.isfinite(sd) or sd < 1e-9:
            sd = 0.0
        sigma_dict[c] = sd
    return DRIBaseline(mu=pd.Series(mu_dict), sigma=pd.Series(sigma_dict))


def trigger_level_from_dri(dri: float | None) -> str:
    try:
        d = float(dri)
    except (TypeError, ValueError):
        return "Unknown"
    if not np.isfinite(d):
        return "Unknown"
    if d < 60:
        return "Normal"
    if d < 75:
        return "Level 1"
    if d < 85:
        return "Level 2"
    return "Level 3"


def _normalize_weights(pairs: list[tuple[float, float]]) -> float | None:
    valid = [(s, float(w)) for s, w in pairs if np.isfinite(s) and w > 0]
    if not valid:
        return None
    wsum = sum(w for _, w in valid)
    if wsum <= 0:
        return None
    return sum(s * (w / wsum) for s, w in valid)


class DRICalculator:
    def compute_daily_dri(
        self,
        daily_metrics: pd.DataFrame,
        toxicity_by_date: pd.Series | None,
        narrative_duplication_by_date: pd.Series | None,
        creator_targeting_by_date: pd.Series | None,
        baseline: DRIBaseline | None = None,
        creator_profile: CreatorProfile | None = None,
        *,
        allow_legacy_news_count_fill: bool = True,
    ) -> pd.DataFrame:
        if daily_metrics.empty or "date" not in daily_metrics.columns:
            nan_frame = daily_metrics.assign(
                raw_dri=np.nan,
                dri=np.nan,
                trigger_level="Unknown",
                creator_vulnerability_multiplier=np.nan,
                dominant_revenue_type="-",
                profile_adjusted=False,
                missing_features="",
                used_features="",
            )
            return nan_frame

        w_adj = resolved_weights_for_profile(creator_profile)
        if creator_profile is not None:
            mult = creator_profile.vulnerability_multiplier()
            dom_type = creator_profile.dominant_revenue_type()
            profile_flag = True
        else:
            mult = 1.0
            dom_type = "-"
            profile_flag = False

        base_line = baseline or build_baseline(daily_metrics)
        work = daily_metrics.sort_values("date").reset_index(drop=True).copy()
        legacy_nc = pd.to_numeric(work["news_count"], errors="coerce") if "news_count" in work.columns else None
        if "external_amplification_count" not in work.columns:
            work["external_amplification_count"] = np.nan
        work["external_amplification_count"] = pd.to_numeric(
            work["external_amplification_count"], errors="coerce"
        )
        if allow_legacy_news_count_fill and legacy_nc is not None:
            work["external_amplification_count"] = work["external_amplification_count"].combine_first(legacy_nc)

        dates_norm = pd.to_datetime(work["date"], errors="coerce").dt.normalize()

        tox = nar = tgt = None
        try:
            if toxicity_by_date is not None and not toxicity_by_date.empty:
                tox = toxicity_by_date.copy()
                tox.index = pd.to_datetime(tox.index).normalize()
                tox = tox.reindex(dates_norm)
            if narrative_duplication_by_date is not None and not narrative_duplication_by_date.empty:
                nar = narrative_duplication_by_date.copy()
                nar.index = pd.to_datetime(nar.index).normalize()
                nar = nar.reindex(dates_norm)
            if creator_targeting_by_date is not None and not creator_targeting_by_date.empty:
                tgt = creator_targeting_by_date.copy()
                tgt.index = pd.to_datetime(tgt.index).normalize()
                tgt = tgt.reindex(dates_norm)
        except Exception as e:
            logger.warning("NLP series reindex skipped: %s", e)

        raw_dri_list: list[float] = []
        adj_dri_list: list[float] = []
        missing_features_rows: list[str] = []
        used_features_rows: list[str] = []

        for i in range(len(work)):
            pairs: list[tuple[float, float]] = []
            present: set[str] = set()

            for key, col, _ in _QUANT_FEATURES:
                if col not in work.columns:
                    continue
                w_use = float(w_adj.get(key, 0.0))
                if w_use <= 0:
                    continue
                val = pd.to_numeric(work.iloc[i][col], errors="coerce")
                try:
                    v = float(val)
                except (TypeError, ValueError):
                    continue
                if not np.isfinite(v):
                    continue
                mu = float(base_line.mu[col]) if col in base_line.mu.index else np.nan
                sd = float(base_line.sigma[col]) if col in base_line.sigma.index else np.nan
                if not np.isfinite(mu) or not np.isfinite(sd):
                    continue
                z = safe_z(v, mu, sd)
                score = z_to_normalized_score(z)
                pairs.append((score, w_use))
                present.add(key)

            if tox is not None:
                tt = tox.iloc[i] if hasattr(tox, "iloc") else float("nan")
                try:
                    ttf = float(tt)
                except (TypeError, ValueError):
                    ttf = float("nan")
                if np.isfinite(ttf):
                    w_t = float(w_adj.get("toxicity_score", 0.0))
                    if w_t > 0:
                        pairs.append((ttf * 100.0, w_t))
                        present.add("toxicity_score")

            if nar is not None:
                nv = nar.iloc[i] if hasattr(nar, "iloc") else float("nan")
                try:
                    nvf = float(nv)
                except (TypeError, ValueError):
                    nvf = float("nan")
                if np.isfinite(nvf):
                    w_n = float(w_adj.get("narrative_duplication_score", 0.0))
                    if w_n > 0:
                        pairs.append((nvf * 100.0, w_n))
                        present.add("narrative_duplication_score")

            if tgt is not None:
                gv = tgt.iloc[i] if hasattr(tgt, "iloc") else float("nan")
                try:
                    gvf = float(gv)
                except (TypeError, ValueError):
                    gvf = float("nan")
                if np.isfinite(gvf):
                    w_g = float(w_adj.get("creator_targeting_context_score", 0.0))
                    if w_g > 0:
                        pairs.append((gvf * 100.0, w_g))
                        present.add("creator_targeting_context_score")

            active = {k for k, wv in w_adj.items() if float(wv) > 0}
            missing_features_rows.append(",".join(sorted(active - present)))
            used_features_rows.append(",".join(sorted(present)))

            agg = _normalize_weights(pairs)
            if agg is None:
                raw_dri_list.append(float("nan"))
                adj_dri_list.append(float("nan"))
            else:
                rr = min(100.0, max(0.0, float(agg)))
                raw_dri_list.append(rr)
                adj_dri_list.append(min(100.0, rr * float(mult)))

        work["raw_dri"] = raw_dri_list
        work["dri"] = adj_dri_list
        work["trigger_level"] = work["dri"].apply(trigger_level_from_dri)
        work["creator_vulnerability_multiplier"] = float(mult)
        work["dominant_revenue_type"] = dom_type
        work["profile_adjusted"] = bool(profile_flag)
        work["missing_features"] = missing_features_rows
        work["used_features"] = used_features_rows
        return work
