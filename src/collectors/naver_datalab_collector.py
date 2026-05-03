"""네이버 데이터랩 통합 검색어 트렌드 POST + CSV fallback."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from src.config import DATA_DIR, get_naver_client_id, get_naver_client_secret

logger = logging.getLogger(__name__)

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"


class NaverDataLabCollector:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        sample_daily_csv: Path | None = None,
    ) -> None:
        self._client_id = (client_id or get_naver_client_id() or "").strip() or None
        self._client_secret = (client_secret or get_naver_client_secret() or "").strip() or None
        self._sample_daily_csv = sample_daily_csv or (DATA_DIR / "sample_daily_metrics.csv")

    def fetch_search_trend(
        self,
        keyword_groups: list[list[str]],
        start_date: date | None,
        end_date: date | None,
        *,
        allow_csv_fallback: bool = True,
    ) -> pd.DataFrame:
        if self._client_id and self._client_secret and start_date and end_date:
            df = self._fetch_via_api(keyword_groups, start_date, end_date)
            if df is not None and not df.empty:
                return df
        if not allow_csv_fallback:
            return pd.DataFrame(columns=["date", "search_index"])
        return self._fetch_via_csv_fallback(start_date, end_date)

    def _fetch_via_api(
        self,
        keyword_groups: list[list[str]],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame | None:
        groups_payload: list[dict[str, object]] = []
        for i, g in enumerate(keyword_groups[:5]):
            ks = [k.strip() for k in g if k.strip()][:20]
            if not ks:
                continue
            groups_payload.append({"groupName": f"g{i}", "keywords": ks})
        if not groups_payload:
            groups_payload = [{"groupName": "default", "keywords": ["키워드"]}]

        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "timeUnit": "date",
            "keywordGroups": groups_payload,
        }
        headers = {
            "X-Naver-Client-Id": self._client_id or "",
            "X-Naver-Client-Secret": self._client_secret or "",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(
                DATALAB_URL,
                headers=headers,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                timeout=40,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("Naver DataLab API failed: %s", e)
            return None

        rows: list[tuple[str, float]] = []
        for res in data.get("results", []):
            for pt in res.get("data", []):
                period = pt.get("period")
                ratio = float(pt.get("ratio", 0) or 0)
                rows.append((period, ratio))

        if not rows:
            return pd.DataFrame(columns=["date", "search_index"])

        mx = max(r for _, r in rows) or 1.0
        out = pd.DataFrame(
            {
                "date": pd.to_datetime([p for p, _ in rows]),
                # ratio를 포화 줄이도록 상대값 → 대략 0~120 스케일
                "search_index": [min(120.0, (r / mx) * 100.0) for _, r in rows],
            }
        )
        return out.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

    def _fetch_via_csv_fallback(
        self,
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        try:
            if not self._sample_daily_csv.exists():
                return pd.DataFrame(columns=["date", "search_index"])
            dm = pd.read_csv(self._sample_daily_csv)
            if "date" not in dm.columns:
                return pd.DataFrame(columns=["date", "search_index"])
            dm["date"] = pd.to_datetime(dm["date"], errors="coerce")
            out = dm[["date", "search_index"]].dropna()
            if start_date is not None:
                out = out[out["date"] >= pd.Timestamp(start_date)]
            if end_date is not None:
                out = out[out["date"] <= pd.Timestamp(end_date)]
            return out.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.warning("Naver CSV fallback failed: %s", e)
            return pd.DataFrame(columns=["date", "search_index"])
