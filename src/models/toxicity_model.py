"""한국어 혐오·독성 신호: 선택적 HF 분류기 + 키워드 휴리스틱 폴백."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)

DEFAULT_HF_TOXICITY_MODEL = "jinkyeongk/kcELECTRA-toxic-detector"
PositiveLabelHF = Literal["LABEL_0", "LABEL_1"]
DEFAULT_POSITIVE_LABEL: PositiveLabelHF = "LABEL_1"


@dataclass
class ToxicityResult:
    toxicity_score: float
    toxic_ratio: float
    top_toxic_texts: list[str]


class KoreanToxicityModel:
    """K-MHaS 이진(혐오/비혐오) HF 모델 또는 키워드 기반 휴리스틱."""

    _TOK = re.compile(
        r"욕|개새|병신|꺼져|죽어|사기|속였|거짓말|역겹|협박|공갈|해명해라|"
        r"녹취|카톡|사생활|신상|파투|망해라|조롱|패고|인신공격|악플|악성",
        re.I,
    )

    def __init__(
        self,
        model_name: str | None = None,
        *,
        use_hf_model: bool = False,
        hf_model_id: str | None = None,
        toxic_prob_threshold: float = 0.5,
        hf_batch_size: int = 16,
        max_length: int = 512,
        top_toxic_n: int = 5,
        positive_label: str = DEFAULT_POSITIVE_LABEL,
        **kwargs: Any,
    ) -> None:
        _ = kwargs
        self.model_name = model_name
        self.use_hf_model = bool(use_hf_model)
        self._hf_id = (hf_model_id or DEFAULT_HF_TOXICITY_MODEL).strip()
        pl = str(positive_label or DEFAULT_POSITIVE_LABEL).strip().upper()
        if pl not in ("LABEL_0", "LABEL_1"):
            logger.warning("positive_label=%r 무시하고 LABEL_1 사용합니다.", positive_label)
            pl = DEFAULT_POSITIVE_LABEL
        self.positive_label = cast("PositiveLabelHF", pl)
        self.toxic_prob_threshold = float(toxic_prob_threshold)
        self.hf_batch_size = max(1, int(hf_batch_size))
        self.max_length = int(max_length)
        self.top_toxic_n = max(1, int(top_toxic_n))

        self.backend: Literal["hf", "keyword"] = "keyword"
        self.hf_fallback_reason: str | None = None
        self._pipe = None

        if self.use_hf_model:
            self._try_init_hf()

        if self.backend == "keyword" and not self.model_name:
            self.model_name = "mock-keyword-v1"

    def _try_init_hf(self) -> None:
        try:
            from transformers import pipeline  # type: ignore[import-untyped]
        except Exception as e:
            self.hf_fallback_reason = f"transformers/torch 미설치 또는 import 실패: {e}"
            logger.warning("KoreanToxicityModel HF 비활성: %s", self.hf_fallback_reason)
            return
        try:
            self._pipe = pipeline(
                "text-classification",
                model=self._hf_id,
                tokenizer=self._hf_id,
                truncation=True,
                max_length=self.max_length,
                top_k=2,
            )
        except Exception as e:
            self._pipe = None
            self.hf_fallback_reason = f"HF 모델 로드 실패({self._hf_id}): {e}"
            logger.warning("%s", self.hf_fallback_reason)
            return
        self.backend = "hf"
        self.model_name = self._hf_id

    def score_texts(self, texts: list[str]) -> ToxicityResult:
        cleaned = [t.strip() for t in texts if t and str(t).strip()]
        if not cleaned:
            return ToxicityResult(0.0, 0.0, [])

        if self.backend == "hf" and self._pipe is not None:
            try:
                return self._score_hf(cleaned)
            except Exception as e:
                logger.warning("HF toxicity inference failed, keyword fallback: %s", e)
                return self._score_keyword(cleaned)
        return self._score_keyword(cleaned)

    def _positive_class_prob(self, pipe_out: object) -> float:
        """파이프라인 단일 샘플 출력에서 `positive_label`(기본 LABEL_1) 클래스 확률."""
        items: list[dict]
        if isinstance(pipe_out, dict):
            items = [pipe_out]
        elif isinstance(pipe_out, list):
            items = [x for x in pipe_out if isinstance(x, dict)]
        else:
            return 0.0
        if not items:
            return 0.0
        tgt = self.positive_label.upper()
        by_lab = {str(d.get("label", "")).upper(): float(d.get("score", 0.0)) for d in items}
        if tgt in by_lab:
            return float(by_lab[tgt])
        if len(by_lab) >= 2:
            return float(by_lab.get(tgt, 0.0))
        if len(items) == 1:
            lab_u = str(items[0].get("label", "")).upper()
            score = float(items[0].get("score", 0.0))
            if lab_u == tgt:
                return float(max(0.0, min(1.0, score)))
            other_u = "LABEL_1" if tgt == "LABEL_0" else "LABEL_0"
            if lab_u == other_u:
                return float(max(0.0, min(1.0, 1.0 - score)))
        return float(items[-1].get("score", 0.0)) if items else 0.0

    def _score_hf(self, cleaned: list[str]) -> ToxicityResult:
        probs: list[float] = []
        paired: list[tuple[float, str]] = []

        for start in range(0, len(cleaned), self.hf_batch_size):
            batch = cleaned[start : start + self.hf_batch_size]
            raw = self._pipe(batch)  # type: ignore[misc]
            if not isinstance(raw, list):
                raw = [raw]
            if len(raw) != len(batch):
                raise RuntimeError("HF pipeline 출력 길이가 배치 크기와 다릅니다.")
            for t, one in zip(batch, raw):
                p = self._positive_class_prob(one)
                probs.append(p)
                paired.append((p, t[:200]))

        avg = sum(probs) / len(probs)
        tox_r = sum(1 for p in probs if p >= self.toxic_prob_threshold) / len(probs)
        top_sorted = [tx for _, tx in sorted(paired, key=lambda x: -x[0])[: self.top_toxic_n]]
        return ToxicityResult(float(avg), float(tox_r), top_sorted)

    def _score_keyword(self, cleaned: list[str]) -> ToxicityResult:
        hits: list[float] = []
        top: list[tuple[float, str]] = []
        for t in cleaned:
            c = len(self._TOK.findall(t))
            s = min(1.0, 0.12 * c + (0.08 if c > 0 else 0.0))
            hits.append(s)
            if c > 0:
                top.append((s, t[:200]))

        avg = sum(hits) / len(hits)
        toxic_ratio = sum(1 for h in hits if h >= 0.2) / len(hits)
        top_sorted = [tx for _, tx in sorted(top, key=lambda x: -x[0])[: self.top_toxic_n]]
        return ToxicityResult(float(avg), float(toxic_ratio), top_sorted)
