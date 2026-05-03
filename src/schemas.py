"""Pydantic 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ContentRiskClassification(BaseModel):
    """콘텐츠 문맥 위험 신호 출력 (0~1 클램프). LLM/mock 공통."""

    target_relevance: float = Field(..., ge=0.0, le=1.0)
    cyber_wrecker_likelihood: float = Field(..., ge=0.0, le=1.0)
    unverified_claim_risk: float = Field(..., ge=0.0, le=1.0)
    privacy_or_threat_risk: float = Field(..., ge=0.0, le=1.0)
    legitimate_criticism_likelihood: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    @field_validator(
        "target_relevance",
        "cyber_wrecker_likelihood",
        "unverified_claim_risk",
        "privacy_or_threat_risk",
        "legitimate_criticism_likelihood",
        mode="before",
    )
    @classmethod
    def _coerce_float(cls, v: object) -> float:
        try:
            return float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError) as e:
            raise ValueError("must be coercible to float") from e

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return []


def creator_targeting_context_score(c: ContentRiskClassification) -> float:
    """피격(타깃팅)·렉카·허위·사생활 위협 정황 등을 종합한 **문맥상 표적화 위험**."""
    harm_max = max(
        c.cyber_wrecker_likelihood,
        c.unverified_claim_risk,
        c.privacy_or_threat_risk,
    )
    return c.target_relevance * harm_max * (1.0 - c.legitimate_criticism_likelihood)


def defamation_privacy_exposure_score(c: ContentRiskClassification) -> float:
    """명예·사생활 노출 성격 신호 평균."""
    return (
        c.unverified_claim_risk
        + c.privacy_or_threat_risk
        + c.cyber_wrecker_likelihood
    ) / 3.0


def content_risk_score(c: ContentRiskClassification) -> float:
    """대시 보드 요약용: 표적화·노출 성격 블렌드."""
    return (
        creator_targeting_context_score(c)
        + defamation_privacy_exposure_score(c)
    ) / 2.0


# 하위 호환 (내부/테스트 참조 가능)
attack_relevance_score = creator_targeting_context_score
defamation_privacy_risk_score = defamation_privacy_exposure_score
