"""크리에이터·수익 구조 프로필 — DRI 및 손해 영향 추정 보정 레이어(공격 분류 목적 아님)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RevenueType = Literal[
    "longform",
    "shorts",
    "sponsorship",
    "donation_membership",
    "live",
    "external",
]


@dataclass
class MonetizationProfile:
    longform_share: float = 0.4
    shorts_share: float = 0.1
    sponsorship_share: float = 0.25
    donation_membership_share: float = 0.15
    live_share: float = 0.05
    external_share: float = 0.05

    def normalize(self) -> MonetizationProfile:
        values = [
            self.longform_share,
            self.shorts_share,
            self.sponsorship_share,
            self.donation_membership_share,
            self.live_share,
            self.external_share,
        ]
        total = sum(max(0.0, float(v)) for v in values)
        if total <= 1e-9:
            return MonetizationProfile(
                longform_share=1 / 6,
                shorts_share=1 / 6,
                sponsorship_share=1 / 6,
                donation_membership_share=1 / 6,
                live_share=1 / 6,
                external_share=1 / 6,
            )

        return MonetizationProfile(
            longform_share=max(0.0, self.longform_share) / total,
            shorts_share=max(0.0, self.shorts_share) / total,
            sponsorship_share=max(0.0, self.sponsorship_share) / total,
            donation_membership_share=max(0.0, self.donation_membership_share) / total,
            live_share=max(0.0, self.live_share) / total,
            external_share=max(0.0, self.external_share) / total,
        )


@dataclass
class CreatorProfile:
    creator_name: str
    subscriber_count: int | None = None
    avg_daily_views: float | None = None
    avg_daily_comments: float | None = None
    content_category: str = "general"

    monetization: MonetizationProfile = field(default_factory=MonetizationProfile)

    platform_concentration_score: float = 0.5
    content_sensitivity_score: float = 0.5
    face_voice_exposure_score: float = 0.5
    fan_community_dependency_score: float = 0.5
    past_attack_history_score: float = 0.3
    response_capacity_score: float = 0.5

    mcn_affiliated: bool = False
    has_legal_pr_support: bool = False

    def vulnerability_multiplier(self) -> float:
        """같은 DRI라도 이 크리에이터에게 상대 위험이 얼마나 큰지(기본 1.0, 약 0.85~1.30)."""
        m = 1.0
        m += 0.10 * self.platform_concentration_score
        m += 0.12 * self.content_sensitivity_score
        m += 0.10 * self.face_voice_exposure_score
        m += 0.08 * self.fan_community_dependency_score
        m += 0.10 * self.past_attack_history_score
        m -= 0.12 * self.response_capacity_score

        if self.mcn_affiliated:
            m -= 0.03
        if self.has_legal_pr_support:
            m -= 0.05

        return max(0.85, min(1.30, m))

    def dominant_revenue_type(self) -> str:
        mt = self.monetization.normalize()
        shares = {
            "longform": mt.longform_share,
            "shorts": mt.shorts_share,
            "sponsorship": mt.sponsorship_share,
            "donation_membership": mt.donation_membership_share,
            "live": mt.live_share,
            "external": mt.external_share,
        }
        return str(max(shares, key=shares.get))


def monetization_share_dict(profile: MonetizationProfile) -> dict[str, float]:
    mt = profile.normalize()
    return {
        "longform": mt.longform_share,
        "shorts": mt.shorts_share,
        "sponsorship": mt.sponsorship_share,
        "donation_membership": mt.donation_membership_share,
        "live": mt.live_share,
        "external": mt.external_share,
    }
