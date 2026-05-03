"""BigKinds OpenAPI 선택형 소스 — 키·URL이 준비되면 POST 호출 후 표준 외부 확산 스키마로 반환."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import requests

from src.config import get_bigkinds_api_key, get_bigkinds_api_url, get_bigkinds_timeout_seconds

logger = logging.getLogger(__name__)


def _series_datetime_naive_kst_normalized(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    if getattr(dt.dtype, "kind", "") == "M" and pd.api.types.is_datetime64tz_dtype(dt.dtype):
        return dt.dt.tz_convert("Asia/Seoul").dt.normalize().dt.tz_localize(None)
    return dt.dt.normalize()


def _standard_raw_columns() -> list[str]:
    return [
        "source_type",
        "query",
        "title",
        "link",
        "originallink",
        "description",
        "pub_date",
        "date",
        "provider",
        "raw_source",
    ]


def _standard_daily_columns() -> list[str]:
    return [
        "date",
        "external_news_count",
        "external_blog_count",
        "external_cafe_count",
        "external_amplification_count",
        "external_source",
    ]


def _empty_raw_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_standard_raw_columns())


def _empty_daily_df(
    start: date | None = None,
    end: date | None = None,
    *,
    counts_as_nan: bool = False,
) -> pd.DataFrame:
    if start is None or end is None:
        return pd.DataFrame(columns=_standard_daily_columns())
    rng = pd.date_range(
        pd.Timestamp(start).normalize(),
        pd.Timestamp(end).normalize(),
        freq="D",
    )
    d = pd.DataFrame({"date": rng.astype("datetime64[ns]")})
    nan_mode = counts_as_nan
    fill = np.nan if nan_mode else 0.0
    d["external_news_count"] = fill
    d["external_blog_count"] = fill
    d["external_cafe_count"] = fill
    d["external_amplification_count"] = fill
    d["external_source"] = "bigkinds" if not nan_mode else ""
    return d


class BigKindsCollector:
    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._api_key = (api_key or get_bigkinds_api_key() or "").strip() or None
        self._api_url = (api_url or get_bigkinds_api_url() or "").strip() or None
        self._timeout = float(timeout_seconds or get_bigkinds_timeout_seconds())

    def configured(self) -> bool:
        return bool(self._api_key and self._api_url)

    def build_search_queries(self, creator_name: str, keywords: list[str]) -> list[str]:
        base = str(creator_name or "").strip()
        if not base:
            base = "모니터링"
        suffixes_fixed = ["", " 협박", " 해명", " 렉카", " 논란", " 폭로"]
        out: list[str] = []
        seen: set[str] = set()
        for suf in suffixes_fixed:
            q = (base + suf).strip()[:255]
            if q and q not in seen:
                seen.add(q)
                out.append(q)
        for k in keywords:
            kk = str(k).strip()
            if not kk:
                continue
            q = f"{base} {kk}".strip()[:255]
            if q and q not in seen:
                seen.add(q)
                out.append(q)
        return out

    def build_payload(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date,
        end_date: date,
        max_results: int,
    ) -> dict[str, Any]:
        """TODO: 승인된 BigKinds 요청 스키마에 맞게 필드명·중첩 구조를 조정합니다."""
        return {
            "monitoring_target": creator_name.strip(),
            "keywords": keywords,
            "published_date_from": start_date.isoformat(),
            "published_date_to": end_date.isoformat(),
            "max_results": int(max_results),
        }

    def parse_response(self, payload_json: dict[str, Any], query: str) -> list[dict[str, Any]]:
        """TODO: 실제 문서 확정 후 `items`/필드 경로 및 날짜 파싱을 정확히 맞춥니다."""
        items: Any = payload_json.get("items")
        if items is None:
            items = payload_json.get("documents")
        if items is None:
            items = payload_json.get("newsList") or payload_json.get("hits") or payload_json.get("data")
        if not isinstance(items, list):
            return []

        rows: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            title = str(
                it.get("title") or it.get("news_subject") or it.get("ttl") or it.get("titl") or ""
            )
            link = str(it.get("url") or it.get("link") or it.get("news_url") or it.get("org_url") or "")
            olink = str(it.get("originallink") or it.get("original_url") or link)
            pub = str(
                it.get("pub_date")
                or it.get("published_at")
                or it.get("date")
                or it.get("news_date")
                or ""
            )
            desc = str(it.get("description") or it.get("snippet") or it.get("lead") or "")
            dt_any: Any = it.get("_parsed_date")  # 호출부에서 채우지 않으면 문자열 파싱
            dt = pd.NaT
            try:
                if dt_any is not None and not pd.isna(dt_any):
                    dt = pd.to_datetime(dt_any, errors="coerce")
                else:
                    dt = pd.to_datetime(pub, errors="coerce")
            except Exception:
                dt = pd.NaT

            rows.append(
                {
                    "source_type": "bigkinds_news",
                    "query": query,
                    "title": title.strip(),
                    "link": link,
                    "originallink": olink,
                    "description": desc[:2000],
                    "pub_date": pub,
                    "date": dt,
                    "provider": "bigkinds",
                    "raw_source": it,
                }
            )
        return rows

    def fetch_articles(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date,
        end_date: date,
        max_results: int = 100,
    ) -> dict[str, Any]:
        qs = self.build_search_queries(creator_name, keywords)
        meta: dict[str, Any] = {
            "bigkinds_status": "missing_key_or_url",
            "bigkinds_error": None,
            "queries": qs,
            "articles_returned": 0,
            "dataframe": None,
        }
        if not self.configured():
            meta["dataframe"] = _empty_raw_df()
            return meta

        merged_rows: list[dict[str, Any]] = []

        try:
            for q in qs:
                payload = self.build_payload(creator_name, keywords, start_date, end_date, max_results)
                payload["primary_query"] = q
                # TODO: Bearer 외 커스텀 헤더(예 X-ACCESS-TOKEN)로 바꿀 수 있음
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                }
                r = requests.post(
                    str(self._api_url),
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    data = {"items": data}
                if not isinstance(data, dict):
                    meta["bigkinds_status"] = "error"
                    meta["bigkinds_error"] = "response_not_json_object"
                    meta["dataframe"] = _empty_raw_df()
                    return meta
                merged_rows.extend(self.parse_response(data, query=q))

        except Exception as e:
            logger.warning("BigKinds API failed: %s", e)
            meta["bigkinds_status"] = "error"
            meta["bigkinds_error"] = str(e)
            meta["dataframe"] = _empty_raw_df()
            return meta

        if not merged_rows:
            df = _empty_raw_df()
            meta["bigkinds_status"] = "feature_excluded"
            meta["dataframe"] = df
            return meta

        df = pd.DataFrame(merged_rows)
        df = df.drop_duplicates(subset=["link"], keep="first")
        meta["bigkinds_status"] = "success"
        meta["articles_returned"] = int(len(df))
        meta["dataframe"] = df
        return meta

    def fetch_external_amplification(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date,
        end_date: date,
        max_results: int = 100,
        *,
        counts_as_nan_on_failure: bool = False,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        fk = self.fetch_articles(creator_name, keywords, start_date, end_date, max_results=max_results)

        qs = fk.get("queries") or []
        status = fk.get("bigkinds_status")
        meta: dict[str, Any] = {
            "bigkinds_status": status,
            "bigkinds_error": fk.get("bigkinds_error"),
            "queries": list(qs),
            "provider": "bigkinds",
        }

        if status != "success" or not isinstance(fk.get("dataframe"), pd.DataFrame):
            raw = fk.get("dataframe") if isinstance(fk.get("dataframe"), pd.DataFrame) else _empty_raw_df()
            daily = _empty_daily_df(
                start_date, end_date, counts_as_nan=counts_as_nan_on_failure
            )
            if not counts_as_nan_on_failure:
                daily["external_source"] = "bigkinds"
            meta.update(
                {
                    "collected_news": int(len(raw)) if not raw.empty else 0,
                    "collected_blog": 0,
                    "collected_cafe": 0,
                    "external_amplification_total": None
                    if counts_as_nan_on_failure
                    else 0.0,
                }
            )
            return raw.reset_index(drop=True) if isinstance(raw, pd.DataFrame) else raw, daily, meta

        raw_df: pd.DataFrame = fk["dataframe"].copy()

        rng_lo = pd.Timestamp(start_date).normalize()
        rng_hi_excl = pd.Timestamp(end_date).normalize() + timedelta(days=1)

        raw_df["_d"] = _series_datetime_naive_kst_normalized(raw_df["date"])
        in_win = pd.notna(raw_df["_d"]) & (raw_df["_d"] >= rng_lo) & (raw_df["_d"] < rng_hi_excl)
        filtered = raw_df.loc[in_win].copy()

        dates = pd.date_range(rng_lo, pd.Timestamp(end_date).normalize(), freq="D")
        daily = pd.DataFrame({"date": dates.astype("datetime64[ns]")})
        daily["external_blog_count"] = 0.0
        daily["external_cafe_count"] = 0.0

        meta["collected_news"] = int(len(raw_df))
        meta["collected_blog"] = 0
        meta["collected_cafe"] = 0

        if filtered.empty and not raw_df.empty:
            meta["note"] = "날짜 파싱/구간 밖 결과만 있음 — 증거는 전체 목록·일별은 0에 가까울 수 있음"

        if not filtered.empty:
            g = filtered.groupby("_d", observed=False).size()
            ix = pd.DatetimeIndex(pd.to_datetime(daily["date"]).dt.normalize())
            gg = pd.to_numeric(g, errors="coerce").reindex(ix, fill_value=0.0)
            daily["external_news_count"] = np.asarray(gg, dtype=float)
        else:
            daily["external_news_count"] = 0.0

        daily["external_source"] = "bigkinds"
        daily["external_amplification_count"] = pd.to_numeric(
            daily["external_news_count"], errors="coerce"
        ).fillna(0.0)

        cols_show = [c for c in ("source_type", "query", "title", "link", "description", "pub_date") if c in raw_df.columns]
        if cols_show:
            out_raw = raw_df.loc[:, cols_show].copy()
        else:
            _std = [c for c in _standard_raw_columns() if c in raw_df.columns and c != "raw_source"]
            out_raw = raw_df[_std].copy() if _std else pd.DataFrame()
        out_raw["date"] = pd.to_datetime(raw_df["_d"], errors="coerce")
        if "provider" in raw_df.columns:
            out_raw["provider"] = raw_df["provider"]
        else:
            out_raw["provider"] = "bigkinds"

        meta["external_amplification_total"] = float(
            pd.to_numeric(daily["external_amplification_count"], errors="coerce").fillna(0).sum()
        )

        return (
            out_raw.sort_values(["date", "source_type"], na_position="last"),
            daily.reset_index(drop=True),
            meta,
        )