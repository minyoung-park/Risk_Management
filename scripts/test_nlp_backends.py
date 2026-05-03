#!/usr/bin/env python3
"""HF 독성 / ST 클러스터 백엔드가 실제로 활성화됐는지와 샘플 점수를 stdout에 출력합니다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.embedding_cluster_model import NarrativeClusterModel  # noqa: E402
from src.models.toxicity_model import (  # noqa: E402
    DEFAULT_POSITIVE_LABEL,
    KoreanToxicityModel,
)

SAMPLES = [
    "오늘 영상 재밌었어요, 응원합니다.",
    "너 진짜 못생겼다",
    "사기 친 거 아니냐, 해명해라",
    "정당한 비판일 수 있다고 생각합니다.",
    "허위 사실로 명예를 훼손했다면 책임져야 한다.",
]


def main() -> int:
    p = argparse.ArgumentParser(description="NLP HF/ST 백엔드 스모크 테스트")
    p.add_argument("--hf", action="store_true", help="HF 독성 모델 시도(use_hf_model=True)")
    p.add_argument("--st", action="store_true", help="SentenceTransformer 군집 시도")
    p.add_argument(
        "--positive-label",
        choices=("LABEL_0", "LABEL_1"),
        default=DEFAULT_POSITIVE_LABEL,
        help="HF 이진 분류에서 ‘위험/긍정’으로 쓸 클래스 (기본 LABEL_1)",
    )
    p.add_argument(
        "--nar-threshold",
        type=float,
        default=0.80,
        help="내러티브 cosine 병합 임계값",
    )
    args = p.parse_args()

    use_hf = bool(args.hf)
    use_st = bool(args.st)
    print("=== Korean Toxicity ===")
    print(f"use_hf_model={use_hf}, positive_label={args.positive_label}")
    tox = KoreanToxicityModel(use_hf_model=use_hf, positive_label=args.positive_label)
    print(f"backend={tox.backend!r} model_name={tox.model_name!r}")
    print(f"hf_fallback_reason={tox.hf_fallback_reason!r}")
    if use_hf and tox.backend != "hf":
        print("[경고] HF를 요청했으나 활성화되지 않았습니다(위 메시지·패키지·네트워크 확인).")
    print()
    print("문장별 positive-class 점수(동일 설정으로 각 1문장 추론):")
    for s in SAMPLES:
        r = tox.score_texts([s])
        print(f"  score={r.toxicity_score:.4f}\t{r.toxic_ratio:.4f}\t{s[:72]!r}")

    agg = tox.score_texts(SAMPLES)
    print()
    print("5문장 일괄:")
    print(f"  평균 점수={agg.toxicity_score:.4f}, toxic_ratio={agg.toxic_ratio:.4f}")
    print(f"  top snippets: {agg.top_toxic_texts[:3]!r}")

    print()
    print("=== Narrative clustering ===")
    print(f"use_sentence_transformer={use_st}, threshold={args.nar_threshold}")
    nar = NarrativeClusterModel(
        similarity_threshold=args.nar_threshold,
        min_samples=3,
        use_sentence_transformer=use_st,
    )
    print(f"backend={nar.backend!r} embedding_model_name={nar.embedding_model_name!r}")
    print(f"st_fallback_reason={nar.st_fallback_reason!r}")
    if use_st and nar.backend != "sentence_transformer":
        print("[경고] ST를 요청했으나 활성화되지 않았습니다(위 메시지·패키지·네트워크 확인).")
    cr = nar.cluster_texts(SAMPLES)
    print(f"narrative_duplication_score={cr.narrative_duplication_score}")
    print(f"largest_cluster_ratio={cr.largest_cluster_ratio}")
    print(f"n_clusters={len(cr.clusters)} labels={cr.labels}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
