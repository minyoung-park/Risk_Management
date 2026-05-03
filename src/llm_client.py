"""LLM 호출 추상화: API 키 없으면 Mock."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import requests

from src.schemas import ContentRiskClassification

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    def classify_content_risk(
        self,
        creator_name: str,
        title: str,
        description: str,
        top_comments: str,
    ) -> dict[str, Any]:
        """LLM 응답을 dict로 반환 (pydantic 검증 전)."""


class MockLLMClient(LLMClient):
    """키워드 휴리스틱 기반 대체 분류."""

    _CYBER = re.compile(
        r"폭로|충격|실체|협박|사기|거짓말|해명|렉카|뒷광고|사칭|조작|낚시|낚시성",
        re.I,
    )
    _UNVERIFIED = re.compile(
        r"루머|소문|추정|의혹|미확인|단독|폭로|허위|가짜뉴스",
        re.I,
    )
    _PRIVACY = re.compile(
        r"카톡|kakao|녹취|사생활|신상|주소|전화번호|협박|협박성|스토킹",
        re.I,
    )
    _LEGIT = re.compile(
        r"공식\s*해명|팩트체크|fact\s*check|반론|법적\s*대응|입장문|클라리피",
        re.I,
    )

    def classify_content_risk(
        self,
        creator_name: str,
        title: str,
        description: str,
        top_comments: str,
    ) -> dict[str, Any]:
        blob = f"{title}\n{description}\n{top_comments}"
        cname = (creator_name or "").strip()

        rel = 0.35
        if cname and cname.lower() in blob.lower():
            rel = 0.75
        elif any(
            p in blob.lower()
            for p in ("크리에이터", "유튜버", "방송", "채널", "스트리머")
        ):
            rel = 0.55

        def hits(pat: re.Pattern[str]) -> int:
            return len(pat.findall(blob))

        cyber = min(0.05 + hits(self._CYBER) * 0.18 + hits(self._UNVERIFIED) * 0.1, 1.0)
        unverified = min(0.05 + hits(self._UNVERIFIED) * 0.22, 1.0)
        privacy = min(0.05 + hits(self._PRIVACY) * 0.2, 1.0)
        legit = min(0.1 + hits(self._LEGIT) * 0.25, 1.0)

        evidence: list[str] = []
        if hits(self._CYBER):
            evidence.append("사이버렉카/선정적 표현 패턴 탐지(키워드)")
        if hits(self._UNVERIFIED):
            evidence.append("미검증 주장·의혹 제기 표현 패턴 탐지(키워드)")
        if hits(self._PRIVACY):
            evidence.append("사생활·협박 정황 키워드 탐지(키워드)")
        if hits(self._LEGIT):
            evidence.append("공식 반박·팩트체크 성격 표현(키워드)")
        if cname and cname.lower() in blob.lower():
            evidence.append("피보험 대상 이름/채널 직접 언급 가능성")
        if not evidence:
            evidence.append("특별 키워드 미매칭 — 기본 점수(mock LLM)")
        evidence = evidence[:12]

        return {
            "target_relevance": rel,
            "cyber_wrecker_likelihood": cyber,
            "unverified_claim_risk": unverified,
            "privacy_or_threat_risk": privacy,
            "legitimate_criticism_likelihood": legit,
            "evidence": evidence,
        }


class OpenAILLMClient(LLMClient):
    """TODO: 운영 시 모델/프롬프트 버전 고정 및 비용 관리."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str | None = None,
    ) -> None:
        from src.config import get_openai_model

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model or get_openai_model()

    def classify_content_risk(
        self,
        creator_name: str,
        title: str,
        description: str,
        top_comments: str,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You estimate whether discussion content exposes a named creator "
                        "to reputational/defamation/threat/coordinated-criticism style risk vs legitimate criticism "
                        "(not factual legal judgment). Respond ONLY JSON with keys: "
                        "target_relevance, cyber_wrecker_likelihood, "
                        "unverified_claim_risk, privacy_or_threat_risk, "
                        "legitimate_criticism_likelihood (each 0..1 floats), evidence (array of short Korean strings)."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "creator_name": creator_name,
                            "title": title,
                            "description": description,
                            "top_comments": top_comments,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        txt = data["choices"][0]["message"]["content"]
        parsed: dict[str, Any] = json.loads(txt)

        parsed.setdefault("target_relevance", 0.0)
        parsed.setdefault("cyber_wrecker_likelihood", 0.0)
        parsed.setdefault("unverified_claim_risk", 0.0)
        parsed.setdefault("privacy_or_threat_risk", 0.0)
        parsed.setdefault("legitimate_criticism_likelihood", 0.0)
        parsed.setdefault("evidence", [])
        return parsed


def generate_adjuster_llm_summary(brief_facts: str, *, timeout: float = 55.0) -> str | None:
    """손해사정 리포트용 짧은 ‘AI 판단 요약’ 섹션(법적 단정 불가 명시 프롬프트). 실패 시 None."""
    from src.config import get_openai_api_key, get_openai_base_url, get_openai_model

    key = get_openai_api_key()
    if not key or not brief_facts.strip():
        return None

    payload = {
        "model": get_openai_model(),
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write a short Markdown subsection (Korean, up to ~12 bullet points max) helping "
                    "insurance adjuster reviewers. Explicitly refuse legal conclusions/payout determination. "
                    "Focus only on reputational/defamation/coordinated negativity risk signals inferred from KPI text. "
                    "No hallucinated facts beyond the provided brief."
                ),
            },
            {"role": "user", "content": brief_facts},
        ],
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            f"{get_openai_base_url()}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"]).strip()
    except Exception as e:
        logger.warning("adjuster LLM summary failed: %s", e)
        return None


def build_llm_client() -> LLMClient:
    """API 키 있으면 OpenAI 호출 시도 대상 클라이언트, 없으면 Mock."""
    from src.config import get_openai_api_key, get_openai_base_url, get_openai_model

    key = get_openai_api_key()
    if not key:
        return MockLLMClient()
    try:
        return OpenAILLMClient(
            api_key=key,
            base_url=get_openai_base_url(),
            model=get_openai_model(),
        )
    except Exception as e:
        logger.warning("OpenAI client init failed, falling back to mock: %s", e)
        return MockLLMClient()


def coerce_classification(raw: dict[str, Any]) -> ContentRiskClassification:
    """LLM/mock dict을 스키마에 맞게 클램프."""
    def f(name: str, default: float = 0.0) -> float:
        try:
            v = float(raw.get(name, default))
        except (TypeError, ValueError):
            v = default
        return max(0.0, min(1.0, v))

    ev = raw.get("evidence", [])
    if isinstance(ev, str):
        ev_list = [ev] if ev.strip() else []
    elif isinstance(ev, list):
        ev_list = [str(x).strip() for x in ev if str(x).strip()]
    else:
        ev_list = []

    return ContentRiskClassification(
        target_relevance=f("target_relevance"),
        cyber_wrecker_likelihood=f("cyber_wrecker_likelihood"),
        unverified_claim_risk=f("unverified_claim_risk"),
        privacy_or_threat_risk=f("privacy_or_threat_risk"),
        legitimate_criticism_likelihood=f("legitimate_criticism_likelihood"),
        evidence=ev_list[:20],
    )
