"""모니터링 상품용 premium proxy — 실제 보험료 확정 아님."""

from __future__ import annotations

from src.creator_profile import CreatorProfile


def estimate_premium_proxy(
    profile: CreatorProfile,
    incident_probability: float,
    expected_response_cost: float,
) -> dict[str, float]:
    """상품 설계·내부 참고용 연간 프리미엄 proxy (원 단위 임의 상수)."""
    monitoring_fee = 600_000.0
    claim_handling_cost = 300_000.0
    risk_margin = 0.15

    p = max(0.0, min(1.0, float(incident_probability)))
    erc = max(0.0, float(expected_response_cost))

    pure_premium = p * erc * profile.vulnerability_multiplier()

    annual = (pure_premium + monitoring_fee + claim_handling_cost) * (1.0 + risk_margin)

    return {
        "pure_premium_proxy": pure_premium,
        "monitoring_fee": monitoring_fee,
        "claim_handling_cost": claim_handling_cost,
        "risk_margin_rate": risk_margin,
        "annual_premium_proxy": annual,
    }
