"""환경 변수 및 실행 설정."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

DATA_DIR: Path = _PROJECT_ROOT / "data"
REPORTS_DIR: Path = _PROJECT_ROOT / "reports"


def get_openai_api_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return key or None


def get_openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def get_youtube_api_key() -> str | None:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    return key or None


def get_naver_client_id() -> str | None:
    return os.getenv("NAVER_CLIENT_ID", "").strip() or None


def get_naver_client_secret() -> str | None:
    return os.getenv("NAVER_CLIENT_SECRET", "").strip() or None


def get_bigkinds_api_key() -> str | None:
    """예약: 실제 Open API 도입 전까지 미사용."""
    key = os.getenv("BIGKINDS_API_KEY", "").strip()
    return key or None


def get_dri_z_score_divisor() -> float:
    """z > 0 을 선형 매핑할 때 분모(기본 8 → 기존 5보다 포화 완만). 환경변수 DRI_Z_SCORE_DIVISOR."""
    raw = os.getenv("DRI_Z_SCORE_DIVISOR", "").strip()
    if not raw:
        return 8.0
    try:
        d = float(raw)
        return d if d > 1e-6 else 8.0
    except ValueError:
        return 8.0
