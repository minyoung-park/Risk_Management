"""반복 내러티브(프레임) 군집: 선택적 한국어 문장 임베딩 + TF-IDF 폴백."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

DEFAULT_ST_MODEL = "upskyy/gte-base-korean"


@dataclass
class NarrativeClusterResult:
    narrative_duplication_score: float
    largest_cluster_ratio: float
    clusters: list[list[str]]
    labels: list[int] = field(default_factory=list)


class NarrativeClusterModel:
    """Sentence-Transformer 임베딩 cosine 유사도 군집 또는 char n-gram TF-IDF."""

    def __init__(
        self,
        similarity_threshold: float = 0.80,
        min_samples: int = 3,
        embedding_model_name: str | None = None,
        *,
        use_sentence_transformer: bool = False,
        st_batch_size: int = 32,
        **kwargs: Any,
    ) -> None:
        _ = kwargs
        self.similarity_threshold = float(similarity_threshold)
        self.min_samples = int(min_samples)
        self.st_batch_size = max(8, int(st_batch_size))
        self._st_id = (embedding_model_name or DEFAULT_ST_MODEL).strip()

        self.use_sentence_transformer = bool(use_sentence_transformer)
        self.backend: Literal["sentence_transformer", "tfidf"] = "tfidf"
        self.st_fallback_reason: str | None = None
        self._st_model = None
        self.embedding_model_name = embedding_model_name or "tfidf-char-wb-v1"

        if self.use_sentence_transformer:
            self._try_init_st()
            if self.backend == "sentence_transformer":
                self.embedding_model_name = self._st_id

    def _try_init_st(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except Exception as e:
            self.st_fallback_reason = f"sentence-transformers 미설치 또는 import 실패: {e}"
            logger.warning("NarrativeClusterModel ST 비활성: %s", self.st_fallback_reason)
            return
        try:
            self._st_model = SentenceTransformer(self._st_id, trust_remote_code=True)
        except Exception as e:
            self._st_model = None
            self.st_fallback_reason = f"ST 모델 로드 실패({self._st_id}): {e}"
            logger.warning("%s", self.st_fallback_reason)
            return
        self.backend = "sentence_transformer"
        self.embedding_model_name = self._st_id

    def cluster_texts(self, texts: list[str]) -> NarrativeClusterResult:
        cleaned = [str(t).strip() for t in texts if str(t).strip()]
        n = len(cleaned)
        if n < self.min_samples:
            return NarrativeClusterResult(float("nan"), float("nan"), [], [-1] * n)

        if self.backend == "sentence_transformer" and self._st_model is not None:
            try:
                return self._cluster_st(cleaned)
            except Exception as e:
                logger.warning("ST clustering failed, TF-IDF fallback: %s", e)

        return self._cluster_tfidf(cleaned)

    def _cluster_st(self, cleaned: list[str]) -> NarrativeClusterResult:
        assert self._st_model is not None
        emb = self._st_model.encode(
            cleaned,
            batch_size=min(self.st_batch_size, len(cleaned)),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        sim = cosine_similarity(emb)
        return self._cluster_from_similarity(sim, cleaned)

    def _cluster_tfidf(self, cleaned: list[str]) -> NarrativeClusterResult:
        try:
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=1, max_features=4096)
            X = vec.fit_transform(cleaned)
            sim = cosine_similarity(X)
        except Exception as e:
            logger.warning("Narrative clustering failed: %s", e)
            n = len(cleaned)
            return NarrativeClusterResult(float("nan"), float("nan"), [], [-1] * n)

        return self._cluster_from_similarity(sim, cleaned)

    def _cluster_from_similarity(
        self,
        sim: np.ndarray,
        cleaned: list[str],
    ) -> NarrativeClusterResult:
        n = len(cleaned)
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
        if largest < 2:
            narrative_duplication_score = 0.0
        else:
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
