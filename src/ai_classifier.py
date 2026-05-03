"""콘텐츠 컨텍스트 분류 — 상위 우선 후보만 고비용 LLM(선택), 나머지 rule/mock."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from statistics import mode, multimode

import numpy as np
import pandas as pd

from src.llm_client import (
    LLMClient,
    MockLLMClient,
    OpenAILLMClient,
    build_llm_client,
    coerce_classification,
)
from src.models.embedding_cluster_model import NarrativeClusterModel
from src.models.toxicity_model import KoreanToxicityModel
from src.schemas import (
    ContentRiskClassification,
    content_risk_score,
    creator_targeting_context_score,
    defamation_privacy_exposure_score,
)

logger = logging.getLogger(__name__)

_HARMFUL_KEYWORD = re.compile(
    r"폭로|충격|실체|협박|사기|거짓말|해명|렉카|뒷광고|사칭|조작|낚시|루머|의혹|"
    r"녹취|카톡|사생활|신상|공갈|허위|가짜뉴스|단독|미확인|스토킹",
    re.I,
)


def _segments(text: str) -> list[str]:
    chunks = [p.strip() for p in re.split(r"[•\|\n／/]+", text or "") if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for c in chunks:
        if len(c) < 4:
            continue
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    if len(out) < 2 and text and len(text.strip()) >= 4:
        return [text.strip()[:1600]]
    return out[:50]


def _harmful_keyword_intensity(blob: str) -> float:
    hits = len(_HARMFUL_KEYWORD.findall(blob or ""))
    return float(min(1.0, 0.08 * hits + (0.1 if hits else 0.0)))


class AIContentRiskClassifier:
    def __init__(
        self,
        client: LLMClient | None = None,
        force_mock: bool = False,
        max_llm_items: int = 10,
    ) -> None:
        self.force_mock = bool(force_mock)
        self.max_llm_items = max(1, int(max_llm_items))
        self._rule_client = MockLLMClient()
        if self.force_mock:
            self._api_client: LLMClient | None = None
        else:
            self._api_client = client or build_llm_client()
        self._toxic = KoreanToxicityModel()

    def classify_row_via_client(
        self,
        llm_client: LLMClient,
        creator_name: str,
        title: str,
        description: str,
        top_comments: str,
    ) -> tuple[ContentRiskClassification, dict[str, float]]:
        from typing import Any

        raw: dict[str, Any]
        try:
            raw = llm_client.classify_content_risk(
                creator_name=creator_name,
                title=title or "",
                description=description or "",
                top_comments=top_comments or "",
            )
        except Exception as e:
            logger.warning("classification client failed — rule fallback: %s", e)
            raw = self._rule_client.classify_content_risk(
                creator_name=creator_name,
                title=title or "",
                description=description or "",
                top_comments=top_comments or "",
            )
        validated = coerce_classification(raw)
        ct = creator_targeting_context_score(validated)
        dp = defamation_privacy_exposure_score(validated)
        extras = {
            "creator_targeting_context_score": ct,
            "defamation_privacy_exposure_score": dp,
            "content_risk_score": content_risk_score(validated),
        }
        return validated, extras

    def classify_dataframe(self, creator_name: str, videos_df: pd.DataFrame) -> pd.DataFrame:
        if videos_df.empty:
            return videos_df.copy()

        work = videos_df.reset_index(drop=True).copy()

        vc = pd.to_numeric(work.get("view_count"), errors="coerce").fillna(0.0).to_numpy(dtype=float)
        cc = pd.to_numeric(work.get("comment_count"), errors="coerce").fillna(0.0).to_numpy(dtype=float)
        vmin, vmax = float(vc.min()), float(vc.max())
        cmin, cmax = float(cc.min()), float(cc.max())

        def _mm(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
            if hi <= lo:
                return np.zeros_like(arr, dtype=float)
            return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)

        nv = _mm(vc, vmin, vmax if vmax > vmin else vmin + 1.0)
        nc = _mm(cc, cmin, cmax if cmax > cmin else cmin + 1.0)

        keyword_scores: list[float] = []
        for _, row in work.iterrows():
            blob = (
                str(row.get("title", "") or "")
                + " "
                + str(row.get("description", "") or "")
                + " "
                + str(row.get("top_comments", "") or "")
            )
            keyword_scores.append(_harmful_keyword_intensity(blob))

        kw = np.array(keyword_scores, dtype=float)

        prio = 0.4 * nv + 0.3 * nc + 0.3 * kw
        work["candidate_priority_score"] = prio.astype(float)

        order = np.argsort(-prio, kind="stable")
        top_positions = set(int(i) for i in order[: self.max_llm_items])

        use_openai_for_top = bool(
            (not self.force_mock)
            and self._api_client is not None
            and isinstance(self._api_client, OpenAILLMClient)
        )

        rows: list[dict[str, object]] = []
        for pos, (_, row) in enumerate(work.iterrows()):
            title = str(row.get("title", "") or "")
            desc = str(row.get("description", "") or "")
            comments = str(row.get("top_comments", "") or "")

            rule_or_api: LLMClient = self._rule_client
            reviewed = False
            if pos in top_positions and use_openai_for_top:
                rule_or_api = self._api_client  # type: ignore[assignment]
                reviewed = True

            clsf, extras = self.classify_row_via_client(
                rule_or_api,
                creator_name=creator_name,
                title=title,
                description=desc,
                top_comments=comments,
            )

            tox_segments = []
            if title.strip():
                tox_segments.append(title.strip()[:360])
            tox_segments.extend(s[:360] for s in _segments(desc))
            tox_segments.extend(s[:360] for s in _segments(comments))

            tr = self._toxic.score_texts(tox_segments)

            rr = dict(row)
            rr["candidate_priority_score"] = float(work.at[pos, "candidate_priority_score"])
            rr["target_relevance"] = clsf.target_relevance
            rr["cyber_wrecker_likelihood"] = clsf.cyber_wrecker_likelihood
            rr["unverified_claim_risk"] = clsf.unverified_claim_risk
            rr["privacy_or_threat_risk"] = clsf.privacy_or_threat_risk
            rr["legitimate_criticism_likelihood"] = clsf.legitimate_criticism_likelihood
            rr["evidence_list"] = clsf.evidence
            rr["creator_targeting_context_score"] = extras["creator_targeting_context_score"]
            rr["defamation_privacy_exposure_score"] = extras["defamation_privacy_exposure_score"]
            rr["content_risk_score"] = extras["content_risk_score"]
            rr["toxicity_score"] = float(tr.toxicity_score)
            rr["comment_chunks"] = _segments(comments)
            rr["llm_context_review"] = reviewed
            rows.append(rr)

        out = pd.DataFrame(rows).reset_index(drop=True)
        out["publish_day"] = pd.to_datetime(out.get("published_at"), errors="coerce").dt.normalize()

        out["narrative_duplication_score"] = np.nan
        out["narrative_cluster_id"] = -1

        nar_model = NarrativeClusterModel(similarity_threshold=0.80, min_samples=3)

        for day_val, chunk in out.groupby("publish_day", dropna=False):
            if pd.isna(day_val):
                continue
            idxs = chunk.index.tolist()
            if len(idxs) == 0:
                continue

            flat_texts: list[str] = []
            owners: list[int] = []
            for i in idxs:
                ch = out.at[i, "comment_chunks"]
                if not isinstance(ch, list):
                    continue
                for frag in ch:
                    flat_texts.append(str(frag)[:400])
                    owners.append(int(i))

            if len(flat_texts) < 3:
                continue

            res = nar_model.cluster_texts(flat_texts)
            dup_val = float(res.narrative_duplication_score)
            if not np.isfinite(dup_val):
                continue

            for i in idxs:
                out.at[i, "narrative_duplication_score"] = dup_val

            row_to_labs: defaultdict[int, list[int]] = defaultdict(list)
            for owner, lb in zip(owners, res.labels):
                row_to_labs[owner].append(int(lb))

            for i in idxs:
                labs = row_to_labs.get(int(i), [])
                if not labs:
                    continue
                try:
                    top_mode = multimode(labs)
                    cid = int(top_mode[0])
                except Exception:
                    try:
                        cid = int(mode(labs))
                    except Exception:
                        cid = int(labs[0])
                out.at[i, "narrative_cluster_id"] = cid

        out = out.drop(columns=[c for c in ("comment_chunks", "publish_day") if c in out.columns])
        out["evidence_str"] = out["evidence_list"].apply(
            lambda x: "; ".join(x) if isinstance(x, list) else ""
        )
        return out.reset_index(drop=True)


def aggregate_nlp_daily(classified_df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """영상별 분류 결과를 발행 일자 기준 시계열로 합산."""
    empty = pd.Series(dtype=float)
    if classified_df.empty or "published_at" not in classified_df.columns:
        return empty, empty, empty

    v = classified_df.copy()
    v["publish_day"] = pd.to_datetime(v["published_at"], errors="coerce").dt.normalize()
    v = v.dropna(subset=["publish_day"]).copy()
    if v.empty:
        return empty, empty, empty

    v["tox"] = pd.to_numeric(v.get("toxicity_score"), errors="coerce")
    v["ct"] = pd.to_numeric(v.get("creator_targeting_context_score"), errors="coerce")
    v["nar"] = pd.to_numeric(v.get("narrative_duplication_score"), errors="coerce")

    g = v.groupby("publish_day", dropna=False)
    toxicity = g["tox"].mean()
    narrative = g["nar"].median()
    targeting = g["ct"].mean()
    return toxicity.astype(float), narrative.astype(float), targeting.astype(float)
