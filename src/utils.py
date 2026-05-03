"""공용 유틸."""

from __future__ import annotations

from src.config import get_dri_z_score_divisor


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def safe_z(value: float, mean: float, std: float) -> float:
    if std is None or std < 1e-9:
        return 0.0
    return (float(value) - mean) / std


def z_to_normalized_score(z: float, divisor: float | None = None) -> float:
    """z >= 0 만 반영 후 [0,100] 클램프. divisor 기본값은 설정(DRI_Z_SCORE_DIVISOR, 통상 8)."""
    z = float(z)
    if z <= 0:
        return 0.0
    d = float(divisor if divisor is not None else get_dri_z_score_divisor())
    if d <= 1e-9:
        d = 8.0
    return min(z / d * 100.0, 100.0)
