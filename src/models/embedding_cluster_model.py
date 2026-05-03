"""TF-IDF 유사도 기반 반복 내러티브(프레임) 군집 — sentence-transformers 교체 TODO."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class NarrativeClusterResult:
    narrative_duplication_score: float
    largest_cluster_ratio: float
    clusters: list[list[str]]
    labels: list[int] = field(default_factory=list)


class NarrativeClusterModel:
    """짧은 한국어 코멘트에 char n-gram TF-IDF를 적용."""

    def __init__(
        self,
        similarity_threshold: float = 0.80,
        min_samples: int = 3,
        embedding_model_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.similarity_threshold = float(similarity_threshold)
        self.min_samples = int(min_samples)
        # TODO: sentence-transformers 멀티링구얼 임베딩 + cosine clustering으로 교체
        self.embedding_model_name = embedding_model_name or "tfidf-char-wb-v1"
        _ = kwargs

    def cluster_texts(self, texts: list[str]) -> NarrativeClusterResult:
        cleaned = [str(t).strip() for t in texts if str(t).strip()]
        n = len(cleaned)
        if n < self.min_samples:
            return NarrativeClusterResult(float("nan"), float("nan"), [], [-1] * n)

        try:
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, max_features=4096)
            X = vec.fit_transform(cleaned)
            sim = cosine_similarity(X)
        except Exception as e:
            logger.warning("Narrative clustering failed: %s", e)
            return NarrativeClusterResult(float("nan"), float("nan"), [], [-1] * n)

        parent = list(range(n))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def unite(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for i in range(n):
            for j in range(i + 1, n):
                if float(sim[i, j]) >= self.similarity_threshold:
                    unite(i, j)

        buckets: dict[int, list[int]] = {}
        for i in range(n):
            r = find(i)
            buckets.setdefault(r, []).append(i)

        clusters_text = [[cleaned[i] for i in idxs] for idxs in buckets.values()]
        sizes = np.array([len(c) for c in clusters_text], dtype=float)
        largest = float(sizes.max()) if sizes.size else 0.0
        largest_ratio = largest / float(n) if n else float("nan")
        narrative_duplication_score = largest_ratio if np.isfinite(largest_ratio) else float("nan")

        labels = [0] * n
        for lab, (_, idxs) in enumerate(sorted(buckets.items(), key=lambda kv: -len(kv[1]))):
            for i in idxs:
                labels[i] = lab

        return NarrativeClusterResult(
            narrative_duplication_score=float(narrative_duplication_score),
            largest_cluster_ratio=float(largest_ratio),
            clusters=clusters_text,
            labels=labels,
        )
