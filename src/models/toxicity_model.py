"""한국어 악성·비방 표현 휴리스틱 (향후 HF 모델 교체 가능)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ToxicityResult:
    toxicity_score: float
    toxic_ratio: float
    top_toxic_texts: list[str]


class KoreanToxicityModel:
    """욕설·비방·협박·사기 프레임 등 키워드 기반 mock 점수."""

    _TOK = re.compile(
        r"욕|개새|병신|꺼져|죽어|사기|속였|거짓말|역겹|협박|공갈|해명해라|"
        r"녹취|카톡|사생활|신상|파투|망해라|조롱|패고|인신공격|악플|악성",
        re.I,
    )

    def __init__(self, model_name: str | None = None, **kwargs: Any) -> None:
        # TODO: transformers pipeline("text-classification", model=...) 등으로 교체 가능
        self.model_name = model_name or "mock-keyword-v1"
        _ = kwargs

    def score_texts(self, texts: list[str]) -> ToxicityResult:
        cleaned = [t.strip() for t in texts if t and str(t).strip()]
        if not cleaned:
            return ToxicityResult(0.0, 0.0, [])

        hits: list[float] = []
        top: list[tuple[float, str]] = []
        for t in cleaned:
            c = len(self._TOK.findall(t))
            # 문장 길이 대비 대략 정규화
            s = min(1.0, 0.12 * c + (0.08 if c > 0 else 0.0))
            hits.append(s)
            if c > 0:
                top.append((s, t[:200]))

        avg = sum(hits) / len(hits)
        toxic_ratio = sum(1 for h in hits if h >= 0.2) / len(hits)
        top_sorted = [tx for _, tx in sorted(top, key=lambda x: -x[0])[:5]]
        return ToxicityResult(float(avg), float(toxic_ratio), top_sorted)
