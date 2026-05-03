"""YouTube Data API v3 수집 + 샘플 CSV fallback.

Quota: search.list 100 units/호출, videos.list·commentThreads.list 1 unit.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config import DATA_DIR, get_youtube_api_key

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


class YouTubeCollector:
    def __init__(
        self,
        api_key: str | None = None,
        fallback_videos_csv: Path | None = None,
        max_comments_videos: int = 15,
        allow_csv_fallback: bool = True,
    ) -> None:
        self._api_key = (api_key or get_youtube_api_key() or "").strip() or None
        self._allow_csv_fallback = bool(allow_csv_fallback)
        if fallback_videos_csv is not None:
            self._fallback_csv = fallback_videos_csv
        elif self._allow_csv_fallback:
            self._fallback_csv = DATA_DIR / "sample_candidate_videos.csv"
        else:
            self._fallback_csv = None
        self._max_comments_videos = max(1, int(max_comments_videos))

    def search_via_api(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        if not self._api_key:
            return pd.DataFrame()
        q_parts = [k for k in keywords if k.strip()][:8]
        if creator_name.strip():
            q_parts = [creator_name.strip()] + q_parts
        q = " ".join(q_parts)[:180] or creator_name.strip() or "news"
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "q": q,
            "maxResults": 50,
            "key": self._api_key,
        }
        if start_date is not None:
            dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            params["publishedAfter"] = dt.isoformat().replace("+00:00", "Z")
        if end_date is not None:
            end_d = end_date + timedelta(days=1)
            dt2 = datetime.combine(end_d, datetime.min.time()).replace(tzinfo=timezone.utc)
            params["publishedBefore"] = dt2.isoformat().replace("+00:00", "Z")

        try:
            r = requests.get(SEARCH_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("YouTube search.list failed: %s", e)
            return pd.DataFrame()

        ids: list[str] = []
        snippet_by_id: dict[str, dict[str, Any]] = {}
        for item in data.get("items", []):
            iid = item.get("id", {})
            if iid.get("kind") != "youtube#video":
                continue
            vid = iid.get("videoId")
            if not vid:
                continue
            ids.append(vid)
            snippet_by_id[vid] = item.get("snippet", {})

        if not ids:
            return pd.DataFrame()

        stats_by_id: dict[str, dict[str, Any]] = {}
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            try:
                rv = requests.get(
                    VIDEOS_URL,
                    params={
                        "part": "statistics,snippet",
                        "id": ",".join(chunk),
                        "key": self._api_key,
                    },
                    timeout=30,
                )
                rv.raise_for_status()
                vdata = rv.json()
            except Exception as e:
                logger.warning("YouTube videos.list failed: %s", e)
                continue
            for it in vdata.get("items", []):
                vid = it.get("id")
                if vid:
                    stats_by_id[vid] = {
                        "statistics": it.get("statistics", {}),
                        "snippet": it.get("snippet", snippet_by_id.get(vid, {})),
                    }

        rows: list[dict[str, Any]] = []
        for idx, vid in enumerate(ids):
            sn = stats_by_id.get(vid, {}).get("snippet") or snippet_by_id.get(vid, {})
            st = stats_by_id.get(vid, {}).get("statistics", {})
            title = sn.get("title", "")
            desc = sn.get("description", "")
            ch = sn.get("channelTitle", "")
            published = sn.get("publishedAt", "")
            vc = int(st.get("viewCount", 0) or 0)
            cc = int(st.get("commentCount", 0) or 0)

            top_c = ""
            if idx < self._max_comments_videos:
                top_c = self._fetch_top_comments_text(vid)

            rows.append(
                {
                    "video_id": vid,
                    "title": title,
                    "description": desc,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "channel_title": ch,
                    "published_at": published,
                    "view_count": vc,
                    "comment_count": cc,
                    "top_comments": top_c,
                }
            )

        df = pd.DataFrame(rows)
        if "published_at" in df.columns:
            df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
            df["published_at"] = df["published_at"].dt.tz_convert(None)
        return df.reset_index(drop=True)

    def _fetch_top_comments_text(self, video_id: str, max_results: int = 20) -> str:
        if not self._api_key:
            return ""
        try:
            rc = requests.get(
                COMMENT_THREADS_URL,
                params={
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": max_results,
                    "order": "relevance",
                    "textFormat": "plainText",
                    "key": self._api_key,
                },
                timeout=25,
            )
            rc.raise_for_status()
            cdata = rc.json()
        except Exception as e:
            logger.debug("commentThreads.list skip %s: %s", video_id, e)
            return ""

        texts: list[str] = []
        for it in cdata.get("items", []):
            sn = it.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            body = sn.get("textDisplay") or sn.get("textOriginal") or ""
            if body:
                texts.append(str(body).replace("\n", " ")[:400])
        joined = " / ".join(texts)[:4000]
        return joined

    def load_from_fallback_csv(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        if not self._allow_csv_fallback:
            return pd.DataFrame()
        try:
            if self._fallback_csv is None or not self._fallback_csv.exists():
                return pd.DataFrame()
            df = pd.read_csv(self._fallback_csv)
            if "published_at" in df.columns:
                df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
            kw = [k.strip().lower() for k in keywords if k.strip()]
            if kw and {"title", "description"}.issubset(df.columns):
                blob = df["title"].fillna("") + " " + df["description"].fillna("")
                pat = "|".join(re.escape(x) for x in kw)
                mask = blob.str.lower().str.contains(pat, regex=True, na=False)
                df = df[mask]
            if start_date is not None and "published_at" in df.columns:
                df = df[df["published_at"].dt.normalize() >= pd.Timestamp(start_date)]
            if end_date is not None and "published_at" in df.columns:
                df = df[df["published_at"].dt.normalize() <= pd.Timestamp(end_date)]
            return df.reset_index(drop=True)
        except Exception as e:
            logger.warning("YouTube CSV fallback failed: %s", e)
            return pd.DataFrame()

    def search_candidate_videos(
        self,
        creator_name: str,
        keywords: list[str],
        start_date: date | None,
        end_date: date | None,
    ) -> pd.DataFrame:
        """API 우선, 실패·빈 결과 시 fallback CSV(api_only에서는 비활성)."""
        api_df = self.search_via_api(creator_name, keywords, start_date, end_date)
        if not api_df.empty:
            return api_df
        return self.load_from_fallback_csv(creator_name, keywords, start_date, end_date)

    def fetch_video_comments(self, video_id: str, max_results: int = 20) -> list[dict[str, Any]]:
        txt = self._fetch_top_comments_text(video_id, max_results=max_results)
        if not txt:
            return []
        return [{"textDisplay": txt}]
