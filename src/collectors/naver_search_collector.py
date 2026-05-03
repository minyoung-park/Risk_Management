"""Naver Search API (뉴스·블로그·카페글) — 외부 확산 proxy 전용."""

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests

from src.config import get_naver_client_id, get_naver_client_secret, get_naver_search_timeout_seconds

logger = logging.getLogger(__name__)

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"
CAFE_URL = "https://openapi.naver.com/v1/search/cafearticle.json"

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    t = _HTML_TAG_RE.sub(" ", html.unescape(s or ""))
    return " ".join(t.split()).strip()


def _series_datetime_naive_kst_normalized(series: pd.Series) -> pd.Series:
    """RFC822(+09:00) 등 tz-aware 값과 naive 구간 Timestamp 비교 오류 방지용."""
    dt = pd.to_datetime(series, errors="coerce")
    if getattr(dt.dtype, "kind", "") == "M" and pd.api.types.is_datetime64tz_dtype(dt.dtype):
        return dt.dt.tz_convert("Asia/Seoul").dt.normalize().dt.tz_localize(None)
    return dt.dt.normalize()


class NaverSearchCollector:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._client_id = (client_id or get_naver_client_id() or "").strip() or None
        self._client_secret = (client_secret or get_naver_client_secret() or "").strip() or None
        self._timeout = float(timeout_seconds or get_naver_search_timeout_seconds())

    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def fetch_news(
        self,
        query: str,
        display: int = 50,
        start: int = 1,
        sort: str = "date",
    ) -> dict[str, Any]:
        return self.fetch_vertical("news", query, display, start, sort)

    def fetch_blogs(
        self,
        query: str,
        display: int = 50,
        start: int = 1,
        sort: str = "date",
    ) -> dict[str, Any]:
        return self.fetch_vertical("blog", query, display, start, sort)

    def fetch_cafe_articles(
        self,
        query: str,
        display: int = 50,
        start: int = 1,
        sort: str = "date",
    ) -> dict[str, Any]:
        return self.fetch_vertical("cafearticle", query, display, start, sort)

    def fetch_vertical(
        self,
        vertical: str,
        query: str,
        display: int = 50,
        start: int = 1,
        sort: str = "date",
    ) -> dict[str, Any]:
        v = vertical.lower().strip()
        if v == "news":
            url = NEWS_URL
        elif v == "blog":
            url = BLOG_URL
        elif v in ("cafe", "cafearticle"):
            url = CAFE_URL
            v = "cafearticle"
        else:
            raise ValueError(f"unknown vertical: {vertical}")

        if not self.configured():
            return {"_error": "missing_credentials", "items": []}

        display = max(1, min(100, int(display)))
        start = max(1, int(start))
        params = {"query": query, "display": display, "start": start, "sort": sort}
        headers = {
            "X-Naver-Client-Id": self._client_id or "",
            "X-Naver-Client-Secret": self._client_secret or "",
        }
        try:
            r = requests.get(f"{url}?{urlencode(params)}", headers=headers, timeout=self._timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("Naver Search %s failed: %s", v, e)
            return {"_error": str(e), "items": []}

        key = "items" if "items" in data else "items"
        items = data.get("items", [])
        return {"_raw": data, "items": items if isinstance(items, list) else []}

    @staticmethod
    def _parse_news_item(query: str, item: dict[str, Any]) -> dict[str, Any]:
        pub = item.get("pubDate") or item.get("pubdate") or ""
        dt = _parse_rfc822_like(pub)
        title = _strip_tags(str(item.get("title", "")))
        desc = _strip_tags(str(item.get("description", "")))
        link = str(item.get("link", "") or "")
        olink = str(item.get("originallink", "") or link)
        return {
            "source_type": "news",
            "query": query,
            "title": title,
            "link": link,
            "originallink": olink,
            "description": desc,
            "pub_date": pub,
            "date": dt,
            "raw_source": item,
        }

    @staticmethod
    def _parse_blog_item(query: str, item: dict[str, Any]) -> dict[str, Any]:
        post = item.get("postdate") or item.get("postDate") or ""
        dt = _parse_yyyymmdd(post) or pd.NaT
        title = _strip_tags(str(item.get("title", "")))
        desc = _strip_tags(str(item.get("description", "")))
        link = str(item.get("link", "") or "")
        pub = post or ""
        return {
            "source_type": "blog",
            "query": query,
            "title": title,
            "link": link,
            "originallink": link,
            "description": desc,
            "pub_date": pub,
            "date": dt,
            "raw_source": item,
        }

    @staticmethod
    def _parse_cafe_item(query: str, item: dict[str, Any]) -> dict[str, Any]:
        title = _strip_tags(str(item.get("title", "")))
        desc = _strip_tags(str(item.get("description", "")))
        link = str(item.get("link", "") or "")
        return {
            "source_type": "cafe",
            "query": query,
            "title": title,
            "link": link,
            "originallink": link,
            "description": desc,
            "pub_date": "",
            "date": pd.NaT,
            "raw_source": item,
        }

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

    def fetch_external_amplification(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date,
        end_date: date,
        max_pages: int = 1,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        """raw_results_df, daily_external_df, meta(status, 오류 등)."""

        meta: dict[str, Any] = {
            "naver_search_status": "missing_key",
            "naver_search_error": None,
            "queries": [],
        }

        if not self.configured():
            meta["naver_search_status"] = "missing_key"
            return (
                pd.DataFrame(
                    columns=[
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
                ),
                pd.DataFrame(
                    columns=[
                        "date",
                        "external_news_count",
                        "external_blog_count",
                        "external_cafe_count",
                        "external_amplification_count",
                        "external_source",
                    ]
                ),
                meta,
            )

        qs = self.build_search_queries(creator_name, keywords)
        meta["queries"] = list(qs)
        meta["naver_search_status"] = "success"

        rows: list[dict[str, Any]] = []
        display = 50

        for q in qs:
            for vert, parser in (
                ("news", self._parse_news_item),
                ("blog", self._parse_blog_item),
                ("cafearticle", self._parse_cafe_item),
            ):
                page_start = 1
                for _ in range(max(1, int(max_pages))):
                    blob = self.fetch_vertical(vert, q, display=display, start=page_start, sort="date")
                    if blob.get("_error"):
                        if meta["naver_search_status"] != "missing_key":
                            meta["naver_search_status"] = "error"
                        meta["naver_search_error"] = str(blob.get("_error"))
                    for it in blob.get("items", []):
                        if not isinstance(it, dict):
                            continue
                        rows.append(parser(q, it))
                    page_start += display
                    if len(blob.get("items", [])) < display:
                        break

        if not rows:
            raw_df = pd.DataFrame(
                columns=[
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
            )
            daily = pd.DataFrame(
                columns=[
                    "date",
                    "external_news_count",
                    "external_blog_count",
                    "external_cafe_count",
                    "external_amplification_count",
                    "external_source",
                ]
            )
            if meta["naver_search_status"] == "success" and not meta.get("naver_search_error"):
                meta["naver_search_status"] = "feature_excluded"
            return raw_df, daily, meta

        raw_df = pd.DataFrame(rows)
        raw_df = raw_df.drop_duplicates(subset=["link"], keep="first")

        rng_lo = pd.Timestamp(start_date).normalize()
        rng_hi_excl = pd.Timestamp(end_date).normalize() + timedelta(days=1)

        raw_df["_d"] = _series_datetime_naive_kst_normalized(raw_df["date"])
        in_win = pd.notna(raw_df["_d"]) & (raw_df["_d"] >= rng_lo) & (raw_df["_d"] < rng_hi_excl)
        filtered = raw_df.loc[in_win].copy()

        dates = pd.date_range(rng_lo, pd.Timestamp(end_date).normalize(), freq="D")
        daily = pd.DataFrame({"date": dates.astype("datetime64[ns]")})
        daily["external_news_count"] = 0.0
        daily["external_blog_count"] = 0.0
        daily["external_cafe_count"] = 0.0

        use_agg = filtered
        if filtered.empty and not raw_df.empty:
            meta["note"] = "날짜 파싱/구간 밖 결과만 있음 — 증거는 전체 목록 표시·일별 집계는 0에 가까울 수 있음"

        meta["collected_news"] = int((raw_df["source_type"] == "news").sum())
        meta["collected_blog"] = int((raw_df["source_type"] == "blog").sum())
        meta["collected_cafe"] = int((raw_df["source_type"] == "cafe").sum())

        if not use_agg.empty:
            g = (
                use_agg.groupby(["_d", "source_type"], observed=False)
                .size()
                .unstack(fill_value=0)
            )
            ix = pd.DatetimeIndex(pd.to_datetime(daily["date"]).dt.normalize())

            def _pull(series_name: str) -> np.ndarray:
                if series_name not in g.columns:
                    return np.zeros(len(daily), dtype=float)
                s = pd.to_numeric(g[series_name], errors="coerce").reindex(ix, fill_value=0.0)
                return np.asarray(s, dtype=float)

            daily["external_news_count"] = _pull("news")
            daily["external_blog_count"] = _pull("blog")
            daily["external_cafe_count"] = _pull("cafe")

        daily["external_amplification_count"] = (
            pd.to_numeric(daily["external_news_count"], errors="coerce").fillna(0)
            + pd.to_numeric(daily["external_blog_count"], errors="coerce").fillna(0)
            + pd.to_numeric(daily["external_cafe_count"], errors="coerce").fillna(0)
        )
        daily["external_source"] = "naver_search"

        cols_show = ["source_type", "query", "title", "link", "description", "pub_date"]
        out_raw = raw_df.loc[:, cols_show].copy()
        out_raw["date"] = pd.to_datetime(raw_df["_d"], errors="coerce")
        out_raw["provider"] = "naver_search"

        meta["external_amplification_total"] = float(
            pd.to_numeric(daily["external_amplification_count"], errors="coerce").fillna(0).sum()
        )

        return out_raw.sort_values(["date", "source_type"], na_position="last"), daily.reset_index(drop=True), meta


def _parse_rfc822_like(s: str) -> Any:
    if not str(s).strip():
        return pd.NaT
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(str(s))
    except Exception:
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S"):
        try:
            return datetime.strptime(str(s).rsplit("+", 1)[0][:25].strip(), fmt[: len(fmt)])
        except Exception:
            continue
    return pd.NaT


def _parse_yyyymmdd(s: str) -> Any:
    t = str(s).strip()
    if len(t) >= 8 and t[:8].isdigit():
        try:
            return datetime.strptime(t[:8], "%Y%m%d")
        except Exception:
            return pd.NaT
    return pd.NaT
