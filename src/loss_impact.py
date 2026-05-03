"""손해 영향 가능 수익원 proxy — 참고 추정값(증빙·사실관계 확인 전제)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.creator_profile import CreatorProfile


def _signal_strength_0_100(dri_daily: pd.DataFrame, column: str) -> float:
    if dri_daily.empty or column not in dri_daily.columns:
        return 0.0
    s = pd.to_numeric(dri_daily[column], errors="coerce").dropna()
    if s.empty:
        return 0.0
    last = float(s.iloc[-1])
    ref = float(s.quantile(0.90))
    if not np.isfinite(ref) or ref < 1e-9:
        ref = float(s.max()) or 1e-9
    return float(min(100.0, 100.0 * last / max(ref, 1e-9)))


def _peak_value(dri_daily: pd.DataFrame, col: str) -> float:
    if dri_daily.empty or col not in dri_daily.columns:
        return 0.0
    x = pd.to_numeric(dri_daily[col], errors="coerce").dropna()
    if x.empty:
        return 0.0
    return float(x.max())


def _to_float_metric(kpis: dict[str, object], key: str) -> float | None:
    v = kpis.get(key)
    if v is None or v == "-":
        return None
    try:
        xf = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(xf):
        return None
    return xf


@dataclass
class LossImpactEstimate:
    affected_revenue_types: list[str]
    revenue_impact_score: float
    suggested_coverage: list[str]
    explanation: list[str]


def estimate_loss_impact(
    profile: CreatorProfile,
    kpis: dict[str, object],
    dri_daily: pd.DataFrame,
) -> LossImpactEstimate:
    mt = profile.monetization.normalize()
    affected: list[str] = []
    coverage: list[str] = []
    explanation: list[str] = []

    peak_adj = float(_peak_value(dri_daily, "dri")) if "dri" in dri_daily.columns else 0.0
    pk = float(_to_float_metric(kpis, "peak_dri") or peak_adj)

    peak_raw = (
        float(_peak_value(dri_daily, "raw_dri"))
        if "raw_dri" in dri_daily.columns
        else float(pk)
    )
    peak_use = max(pk, peak_raw, peak_adj)

    news_spike = _signal_strength_0_100(dri_daily, "news_count")
    search_spike = _signal_strength_0_100(dri_daily, "search_index")

    mean_tx = _to_float_metric(kpis, "mean_toxicity_score")
    toxicity_signal = mean_tx if mean_tx is not None else 0.0

    if mt.sponsorship_share >= 0.25 and (news_spike > 60 or search_spike > 60):
        affected.append("advertising_sponsorship")
        coverage.append("광고·협찬 계약 손실 특약 검토")
        explanation.append(
            "광고·협찬 비중이 높고 검색/기사 확산이 커 브랜드 세이프티 리스크가 커 보입니다."
        )

    if mt.donation_membership_share + mt.live_share >= 0.25 and toxicity_signal > 0.3:
        affected.append("donation_membership")
        coverage.append("후원·멤버십 이탈 모니터링")
        explanation.append(
            "팬덤 기반 수익 비중이 높고 댓글 공격성 지표가 올라 커뮤니티 이탈 가능성을 점검할 수 있습니다."
        )

    if mt.longform_share + mt.shorts_share >= 0.5 and peak_use > 75:
        affected.append("platform_revenue")
        coverage.append("수익중단 특약 검토")
        explanation.append(
            "플랫폼 조회수 기반 수익 비중이 높고 DRI 피크가 높아 조회수·업로드 활동 변화 확인이 필요합니다."
        )

    if not affected:
        affected.append("response_cost")
        coverage.append("기본 긴급대응비 담보")
        explanation.append(
            "현재 공개 지표상 직접 수익손실 패턴보다는 긴급대응·법무·PR 비용 중심 검토가 적절할 수 있습니다."
        )

    score = min(1.0, peak_use / 100.0)
    return LossImpactEstimate(
        affected_revenue_types=affected,
        revenue_impact_score=score,
        suggested_coverage=coverage,
        explanation=explanation,
    )
