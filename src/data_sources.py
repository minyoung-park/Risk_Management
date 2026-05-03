"""csv_mock | live_api | hybrid 데이터 소스 조합 및 collector 호출."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from src.collectors.bigkinds_collector import BigKindsCollector
from src.collectors.naver_datalab_collector import NaverDataLabCollector
from src.collectors.naver_search_collector import NaverSearchCollector
from src.collectors.public_channel_analytics_collector import PublicChannelAnalyticsCollector
from src.collectors.youtube_collector import YouTubeCollector
from src.data_loader import filter_metrics_by_dates, load_candidate_videos, load_daily_metrics


def overlay_series_by_date(
    metrics_df: pd.DataFrame,
    patch_df: pd.DataFrame,
    value_col: str,
) -> pd.DataFrame:
    if patch_df.empty or value_col not in patch_df.columns:
        return metrics_df
    m = metrics_df.copy()
    p = patch_df[["date", value_col]].dropna(subset=["date"]).copy()
    m["date"] = pd.to_datetime(m["date"], errors="coerce").dt.normalize()
    p["date"] = pd.to_datetime(p["date"], errors="coerce").dt.normalize()
    pidx = p.set_index("date")[value_col]
    mi = m.set_index("date")
    if value_col not in mi.columns:
        mi[value_col] = pd.NA
    mi[value_col] = pidx.combine_first(mi[value_col])
    return mi.reset_index()


def overlay_multi_channel_cols(metrics_df: pd.DataFrame, ch_df: pd.DataFrame) -> pd.DataFrame:
    if ch_df.empty:
        return metrics_df
    m = metrics_df.copy()
    ch = ch_df.copy()
    m["date"] = pd.to_datetime(m["date"], errors="coerce").dt.normalize()
    ch["date"] = pd.to_datetime(ch["date"], errors="coerce").dt.normalize()
    cols = [c for c in ch.columns if c != "date"]
    sub = ch[["date"] + cols].copy()

    merged = m.merge(sub, on="date", how="left", suffixes=("", "_pch"))
    drops: list[str] = []
    for c in cols:
        pc = f"{c}_pch"
        if pc not in merged.columns:
            continue
        if c in merged.columns:
            merged[c] = merged[pc].combine_first(merged[c])
        else:
            merged[c] = merged[pc]
        drops.append(pc)

    merged = merged.drop(columns=[d for d in drops if d in merged.columns]).sort_values(
        "date"
    ).reset_index(drop=True)
    return merged


def youtube_aggregate_daily(videos_df: pd.DataFrame) -> pd.DataFrame:
    if videos_df.empty:
        return pd.DataFrame()
    v = videos_df.copy()
    if "video_id" not in v.columns:
        v["video_id"] = range(len(v))

    v["published_at"] = pd.to_datetime(v["published_at"], errors="coerce")
    v["date"] = v["published_at"].dt.normalize()
    v["view_count"] = pd.to_numeric(v.get("view_count"), errors="coerce").fillna(0)
    v["comment_count"] = pd.to_numeric(v.get("comment_count"), errors="coerce").fillna(0)
    return (
        v.dropna(subset=["date"])
        .groupby("date", dropna=False)
        .agg(
            candidate_video_count=("video_id", "count"),
            candidate_video_total_views=("view_count", "sum"),
            candidate_video_comment_count=("comment_count", "sum"),
        )
        .reset_index()
    )


def overlay_youtube_aggregates(metrics_df: pd.DataFrame, videos_df: pd.DataFrame) -> pd.DataFrame:
    agg = youtube_aggregate_daily(videos_df)
    if agg.empty:
        return metrics_df

    cols = ["candidate_video_count", "candidate_video_total_views", "candidate_video_comment_count"]
    m = metrics_df.copy()
    m["date"] = pd.to_datetime(m["date"], errors="coerce").dt.normalize()
    agg["date"] = pd.to_datetime(agg["date"], errors="coerce").dt.normalize()

    merged = m.merge(agg, on="date", how="left", suffixes=("", "_yt"))
    for c in cols:
        alt = f"{c}_yt"
        if alt in merged.columns:
            if c not in merged.columns:
                merged[c] = merged[alt]
            else:
                merged[c] = merged[alt].combine_first(merged[c])
            merged = merged.drop(columns=[alt])
    return merged.sort_values("date").reset_index(drop=True)


def dedupe_concat_videos(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    if a.empty:
        return b.copy()
    if b.empty:
        return a.copy()
    out = pd.concat([a, b], ignore_index=True)
    if "video_id" in out.columns:
        return out.drop_duplicates(subset=["video_id"], keep="last").reset_index(drop=True)
    return out


def get_naver_configured() -> bool:
    from src.config import get_naver_client_id, get_naver_client_secret

    return bool(get_naver_client_id() and get_naver_client_secret())


def canonicalize_external_amp_columns(
    metrics_df: pd.DataFrame,
    *,
    allow_legacy_news_count: bool = True,
    allow_breakdown_to_total: bool = True,
) -> pd.DataFrame:
    """레거시 `news_count`/naver_* ↔ 표준 external_* 교차 보간, `external_amplification_count` 정합성."""
    m = metrics_df.copy()
    if m.empty:
        return m

    for col in (
        "external_news_count",
        "external_blog_count",
        "external_cafe_count",
        "naver_news_count",
        "naver_blog_count",
        "naver_cafe_count",
    ):
        if col not in m.columns:
            m[col] = np.nan

    if "external_amplification_count" not in m.columns:
        m["external_amplification_count"] = np.nan

    en = pd.to_numeric(m["external_news_count"], errors="coerce")
    nn = pd.to_numeric(m["naver_news_count"], errors="coerce")
    m["external_news_count"] = en.combine_first(nn)
    m["naver_news_count"] = nn.combine_first(en)

    eb = pd.to_numeric(m["external_blog_count"], errors="coerce")
    nb = pd.to_numeric(m["naver_blog_count"], errors="coerce")
    m["external_blog_count"] = eb.combine_first(nb)
    m["naver_blog_count"] = nb.combine_first(eb)

    ec = pd.to_numeric(m["external_cafe_count"], errors="coerce")
    ncaf = pd.to_numeric(m["naver_cafe_count"], errors="coerce")
    m["external_cafe_count"] = ec.combine_first(ncaf)
    m["naver_cafe_count"] = ncaf.combine_first(ec)

    ea = pd.to_numeric(m["external_amplification_count"], errors="coerce")

    legacy = pd.to_numeric(m["news_count"], errors="coerce") if "news_count" in m.columns else None
    if allow_legacy_news_count and legacy is not None:
        ea = ea.combine_first(legacy)
        m["external_news_count"] = m["external_news_count"].combine_first(legacy)

    breakdown_sum = (
        pd.to_numeric(m["external_news_count"], errors="coerce")
        + pd.to_numeric(m["external_blog_count"], errors="coerce")
        + pd.to_numeric(m["external_cafe_count"], errors="coerce")
    )

    if allow_breakdown_to_total:
        ea = ea.combine_first(breakdown_sum)
    m["external_amplification_count"] = ea
    return m


def normalize_external_amp_source(value: object) -> str:
    v = str(value or "naver_search").strip().lower()
    return v if v in ("naver_search", "bigkinds", "auto") else "naver_search"


def _summarize_daily_external_amp(daily: pd.DataFrame) -> float | None:
    if daily.empty or "external_amplification_count" not in daily.columns:
        return None
    return float(pd.to_numeric(daily["external_amplification_count"], errors="coerce").fillna(0).sum())


def fetch_external_amp_resolved(
    *,
    creator_name: str,
    keywords: list[str],
    analysis_start_date: date,
    analysis_end_date: date,
    requested_source_raw: object,
    fallback_to_naver_override: bool | None,
    bigkinds_nan_on_failure: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    from src.config import get_external_amp_fallback_to_naver, get_external_amp_source

    req = normalize_external_amp_source(requested_source_raw or get_external_amp_source())
    fb = fallback_to_naver_override
    if fb is None:
        fb = get_external_amp_fallback_to_naver()

    ns_col = NaverSearchCollector()
    bk_col = BigKindsCollector()
    naver_ok = ns_col.configured()
    bk_ok = bk_col.configured()

    resolver_meta: dict[str, object] = {
        "external_amp_source_requested": req,
        "external_amp_source_used": None,
        "external_amp_status": "pending",
        "external_amp_error": None,
        "bigkinds_configured": bk_ok,
        "naver_search_configured": naver_ok,
        "fallback_to_naver_occurred": False,
        "bigkinds_status": None,
        "bigkinds_error": None,
        "naver_search_status": None,
        "naver_search_error": None,
        "naver_queries": [],
        "raw_search_results_df": pd.DataFrame(),
        "daily_external_df": pd.DataFrame(),
        "collected_news": 0,
        "collected_blog": 0,
        "collected_cafe": 0,
        "external_amplification_total": None,
        "external_amp_fallback_to_naver_requested": fb,
        "provider_note": "",
    }

    def apply_naver_to_meta(raw: pd.DataFrame, daily: pd.DataFrame, nm: dict[str, object]) -> None:
        resolver_meta.update(
            {
                "raw_search_results_df": raw,
                "daily_external_df": daily,
                "naver_search_status": nm.get("naver_search_status"),
                "naver_search_error": nm.get("naver_search_error"),
                "naver_queries": nm.get("queries") or [],
                "collected_news": int(nm.get("collected_news", 0) or 0),
                "collected_blog": int(nm.get("collected_blog", 0) or 0),
                "collected_cafe": int(nm.get("collected_cafe", 0) or 0),
                "external_amplification_total": nm.get(
                    "external_amplification_total", _summarize_daily_external_amp(daily)
                ),
            }
        )

    def apply_bigkinds_to_meta(raw: pd.DataFrame, daily: pd.DataFrame, bm: dict[str, object]) -> None:
        resolver_meta.update(
            {
                "raw_search_results_df": raw,
                "daily_external_df": daily,
                "bigkinds_status": bm.get("bigkinds_status"),
                "bigkinds_error": bm.get("bigkinds_error"),
                "naver_queries": bm.get("queries") or [],
                "collected_news": int(bm.get("collected_news", 0) or 0),
                "collected_blog": int(bm.get("collected_blog", 0) or 0),
                "collected_cafe": int(bm.get("collected_cafe", 0) or 0),
                "external_amplification_total": bm.get(
                    "external_amplification_total", _summarize_daily_external_amp(daily)
                ),
            }
        )

    def run_naver() -> tuple[pd.DataFrame, pd.DataFrame]:
        raw, daily, nm = ns_col.fetch_external_amplification(
            creator_name,
            keywords,
            analysis_start_date,
            analysis_end_date,
            max_pages=1,
        )
        apply_naver_to_meta(raw, daily, nm)
        resolver_meta["external_amp_source_used"] = "naver_search"
        st = resolver_meta["naver_search_status"]
        if st == "missing_key":
            resolver_meta["external_amp_status"] = "missing_credentials_naver"
        elif st == "error":
            resolver_meta["external_amp_status"] = "error_naver"
            resolver_meta["external_amp_error"] = resolver_meta.get("naver_search_error")
        elif st == "feature_excluded":
            resolver_meta["external_amp_status"] = "success_empty_naver"
        else:
            resolver_meta["external_amp_status"] = "success_naver"
        return raw, daily

    def run_bigkinds() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
        raw, daily, bm = bk_col.fetch_external_amplification(
            creator_name,
            keywords,
            analysis_start_date,
            analysis_end_date,
            max_results=100,
            counts_as_nan_on_failure=bigkinds_nan_on_failure,
        )
        apply_bigkinds_to_meta(raw, daily, bm)
        return raw, daily, bm

    if req == "naver_search":
        run_naver()
        return (
            resolver_meta["raw_search_results_df"],
            resolver_meta["daily_external_df"],
            resolver_meta,
        )

    if req == "bigkinds":
        if not bk_ok:
            resolver_meta["external_amp_status"] = "missing_credentials_bigkinds"
            resolver_meta["external_amp_error"] = "BIGKINDS_API_KEY 또는 BIGKINDS_API_URL 미설정"
            if fb and naver_ok:
                resolver_meta["fallback_to_naver_occurred"] = True
                resolver_meta["provider_note"] = (
                    "BigKinds 자격 미설정으로 Naver Search API로 fallback 했습니다."
                )
                run_naver()
            elif fb and not naver_ok:
                resolver_meta["external_amp_status"] = "missing_credentials"
                resolver_meta["external_amp_error"] = "BigKinds 미설정이며 Naver 자격도 없어 외부 확산 미수집"
            return (
                resolver_meta["raw_search_results_df"],
                resolver_meta["daily_external_df"],
                resolver_meta,
            )
        raw_b, daily_b, bm = run_bigkinds()
        bst = bm.get("bigkinds_status")
        resolver_meta["external_amp_source_used"] = "bigkinds"
        if bst in ("success", "feature_excluded"):
            resolver_meta["external_amp_status"] = "success_bigkinds"
            return raw_b, daily_b, resolver_meta

        resolver_meta["external_amp_status"] = f"error_bigkinds:{bst}"
        resolver_meta["external_amp_error"] = bm.get("bigkinds_error")
        if fb and naver_ok:
            resolver_meta["fallback_to_naver_occurred"] = True
            resolver_meta["provider_note"] = (
                "BigKinds API 호출 실패로 Naver Search API를 fallback 데이터 소스로 사용했습니다."
            )
            run_naver()
        elif fb and not naver_ok:
            resolver_meta["external_amp_status"] = "error_no_fallback"
            resolver_meta["external_amp_error"] = (
                f"{bm.get('bigkinds_error') or bst}; Naver 자격 없음"
            )
        return raw_b, daily_b, resolver_meta

    if req == "auto":
        if bk_ok:
            raw_b, daily_b, bm = run_bigkinds()
            bst = bm.get("bigkinds_status")
            if bst in ("success", "feature_excluded"):
                resolver_meta["external_amp_source_used"] = "bigkinds"
                resolver_meta["external_amp_status"] = "success_bigkinds_auto"
                return raw_b, daily_b, resolver_meta
            resolver_meta["external_amp_error"] = bm.get("bigkinds_error")
            if fb and naver_ok:
                resolver_meta["fallback_to_naver_occurred"] = True
                resolver_meta["provider_note"] = (
                    "BigKinds API 호출 실패로 Naver Search API를 fallback 데이터 소스로 사용했습니다."
                )
                run_naver()
                return (
                    resolver_meta["raw_search_results_df"],
                    resolver_meta["daily_external_df"],
                    resolver_meta,
                )
            resolver_meta["external_amp_source_used"] = "bigkinds"
            resolver_meta["external_amp_status"] = f"failed_bigkinds_auto:{bst}"
            return raw_b, daily_b, resolver_meta

        resolver_meta["external_amp_source_used"] = "naver_search"
        run_naver()
        return (
            resolver_meta["raw_search_results_df"],
            resolver_meta["daily_external_df"],
            resolver_meta,
        )

    run_naver()
    return (
        resolver_meta["raw_search_results_df"],
        resolver_meta["daily_external_df"],
        resolver_meta,
    )


def overlay_metrics_cols_from_daily(
    metrics_df: pd.DataFrame,
    daily_patch: pd.DataFrame,
    value_cols: list[str],
) -> pd.DataFrame:
    """날짜 기준 숫자 열 병합(각 열당 overlay_series_by_date)."""
    m = metrics_df
    if daily_patch.empty or not value_cols:
        return m
    for col in value_cols:
        if col not in daily_patch.columns:
            continue
        chunk = daily_patch[["date", col]].dropna(subset=["date"]).copy()
        m = overlay_series_by_date(m, chunk, col)
    return m


def build_naver_datalab_keyword_groups(creator_name: str) -> list[list[str]]:
    """Naver DataLab keyword group: 크리에이터명 + 주제 접미(협박·해명·렉카·논란). 각 그룹 1키워드."""
    base = str(creator_name or "").strip() or "모니터링"
    suffixes = ("", " 협박", " 해명", " 렉카", " 논란")
    groups: list[list[str]] = []
    for suf in suffixes:
        kw = (base + suf).strip()
        groups.append([kw[:30]])
    return groups[:5]


def _daily_metrics_nan_skeleton(start_d: date, end_d: date) -> pd.DataFrame:
    """api_only: CSV 뼈대 없이 날짜 축만 두고 수치는 결측으로 둠."""
    dr = pd.date_range(
        pd.Timestamp(start_d).normalize(),
        pd.Timestamp(end_d).normalize(),
        freq="D",
    )
    out = pd.DataFrame({"date": dr})
    for c in (
        "search_index",
        "external_news_count",
        "external_blog_count",
        "external_cafe_count",
        "external_amplification_count",
        "candidate_video_count",
        "candidate_video_total_views",
        "candidate_video_comment_count",
        "creator_channel_daily_views",
        "creator_channel_subscriber_change",
        "news_count",
        "naver_news_count",
        "naver_blog_count",
        "naver_cafe_count",
    ):
        out[c] = np.nan
    return out


def resolve_metrics_and_videos(
    *,
    data_source_mode: str,
    metrics_csv_path: Path,
    videos_csv_path: Path,
    creator_name: str,
    keywords: list[str],
    analysis_start_date: date,
    analysis_end_date: date,
    channel_url: str,
    analytics_manual_csv_path: Path | None,
    analytics_provider: str,
    external_amp_source: str | None = None,
    external_amp_fallback_to_naver: bool | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict[str, object]]:
    from src.config import (
        get_external_amp_fallback_to_naver,
        get_external_amp_source,
        get_youtube_api_key,
    )

    notes: list[str] = []
    strict = data_source_mode == "api_only"

    _bk_g = BigKindsCollector()
    _nv_g = NaverSearchCollector()
    resolver_meta: dict[str, object] = {
        "naver_search_status": None,
        "naver_search_error": None,
        "bigkinds_status": None,
        "bigkinds_error": None,
        "naver_queries": [],
        "raw_search_results_df": pd.DataFrame(),
        "daily_external_df": pd.DataFrame(),
        "collected_news": 0,
        "collected_blog": 0,
        "collected_cafe": 0,
        "external_amplification_total": None,
        "external_amp_source_requested": normalize_external_amp_source(
            external_amp_source or get_external_amp_source()
        ),
        "external_amp_source_used": None,
        "external_amp_status": None,
        "external_amp_error": None,
        "bigkinds_configured": _bk_g.configured(),
        "naver_search_configured": _nv_g.configured(),
        "fallback_to_naver_occurred": False,
        "external_amp_fallback_to_naver_requested": (
            get_external_amp_fallback_to_naver()
            if external_amp_fallback_to_naver is None
            else external_amp_fallback_to_naver
        ),
        "provider_note": "",
        "csv_fallback_used": not strict,
        "youtube_api_status": None,
        "naver_datalab_status": None,
        "api_only_missing_features": [],
    }

    if data_source_mode == "csv_mock":
        csv_metrics = load_daily_metrics(metrics_csv_path)
        csv_videos = load_candidate_videos(videos_csv_path)
        cm = canonicalize_external_amp_columns(csv_metrics.copy())
        resolver_meta["csv_fallback_used"] = True
        resolver_meta["youtube_api_status"] = "n_a_csv_mock"
        resolver_meta["naver_datalab_status"] = "n_a_csv_mock"
        return cm, csv_videos.copy(), notes, resolver_meta

    if strict:
        csv_metrics = pd.DataFrame()
        csv_videos = pd.DataFrame()
    else:
        csv_metrics = load_daily_metrics(metrics_csv_path)
        csv_videos = load_candidate_videos(videos_csv_path)

    yt = YouTubeCollector(
        fallback_videos_csv=(videos_csv_path if not strict else None),
        allow_csv_fallback=not strict,
    )
    naver = NaverDataLabCollector(sample_daily_csv=metrics_csv_path)

    prov = analytics_provider if analytics_provider in (
        "manual_csv",
        "socialblade",
        "vling",
        "playboard",
    ) else "manual_csv"

    pch = PublicChannelAnalyticsCollector(
        provider=prov,
        manual_metrics_csv=analytics_manual_csv_path if analytics_manual_csv_path else None,
        fallback_daily_csv=metrics_csv_path,
        disallow_csv_reads=strict,
    )

    api_videos = yt.search_via_api(creator_name, keywords, analysis_start_date, analysis_end_date)

    if not (get_youtube_api_key() or "").strip():
        resolver_meta["youtube_api_status"] = "missing_key"
    elif api_videos.empty:
        resolver_meta["youtube_api_status"] = "empty"
    else:
        resolver_meta["youtube_api_status"] = "success"

    kg = build_naver_datalab_keyword_groups(creator_name)
    notes.append(
        "Naver DataLab 검색조건 그룹: 크리에이터명 단독 +「크리에이터명 협박/해명/렉카/논란」(각 1키워드 그룹)."
    )

    nv_trend = naver.fetch_search_trend(
        kg,
        analysis_start_date,
        analysis_end_date,
        allow_csv_fallback=not strict,
    )

    if strict:
        if not nv_trend.empty:
            resolver_meta["naver_datalab_status"] = "success"
        elif get_naver_configured():
            resolver_meta["naver_datalab_status"] = "missing"
        else:
            resolver_meta["naver_datalab_status"] = "missing_credentials"
    else:
        resolver_meta["naver_datalab_status"] = (
            "success" if not nv_trend.empty else ("csv_fallback" if not get_naver_configured() else "missing")
        )

    raw_ext, daily_ext, resolver_meta = fetch_external_amp_resolved(
        creator_name=creator_name,
        keywords=keywords,
        analysis_start_date=analysis_start_date,
        analysis_end_date=analysis_end_date,
        requested_source_raw=external_amp_source,
        fallback_to_naver_override=external_amp_fallback_to_naver,
        bigkinds_nan_on_failure=strict,
    )

    if resolver_meta.get("provider_note"):
        notes.append(str(resolver_meta["provider_note"]))

    eu = resolver_meta.get("external_amp_source_used")
    fb_flag = bool(resolver_meta.get("fallback_to_naver_occurred", False))

    if eu == "bigkinds":
        bss = resolver_meta.get("bigkinds_status")
        nb = resolver_meta["collected_blog"]
        nc = resolver_meta["collected_cafe"]
        news_n = resolver_meta["collected_news"]
        if not fb_flag:
            notes.append(
                f"BigKinds 외부 확산 수집(뉴스 중심 원시 근처 {news_n}건 · blog/cafe proxy {nb}/{nc}). 상태: `{bss}`"
            )
    elif eu == "naver_search":
        st = resolver_meta["naver_search_status"]
        if st == "missing_key":
            notes.append("Naver Search API: 자격 미설정 — 외부 확산 지표 미수집(결측).")
        elif st == "error":
            notes.append(f"Naver Search API 오류 — {resolver_meta['naver_search_error']}")
        elif st == "feature_excluded":
            notes.append("Naver Search API: 응답 없음 또는 빈 결과 — 외부 확산 증거·일별 집계 확인.")
        else:
            notes.append(
                f"Naver Search 결과 수신(뉴스·블로그·카페 원시 근처 "
                f"{resolver_meta['collected_news'] + resolver_meta['collected_blog'] + resolver_meta['collected_cafe']}건)."
            )
    else:
        if resolver_meta.get("external_amp_error"):
            notes.append(f"외부 확산 미수집 또는 중단 — {resolver_meta.get('external_amp_error')}")

    ch_df = pch.fetch_public_channel_metrics(channel_url, analysis_start_date, analysis_end_date)

    if strict and api_videos.empty:
        notes.append(
            "api_only: YouTube Data API 결과 없음 — 샘플 후보 영상 CSV로 대체하지 않습니다(결측)."
        )

    elif api_videos.empty:
        notes.append(
            "YouTube Data API 결과 없음 — 키·쿼터·키워드를 확인하세요. 후보 영상 CSV를 사용합니다."
        )

    else:
        notes.append(f"YouTube API 후보 {len(api_videos)}건 로드.")

    if strict:
        notes.append(
            "Naver DataLab: api_only 모드로 CSV 검색추이 보조를 사용하지 않습니다."
        )
    elif get_naver_configured():
        notes.append("Naver DataLab: 자격증명 설정됨(성공 시 API, 실패 시 CSV 보조)")
    else:
        notes.append("Naver DataLab: 클라우드 미설정 — CSV 검색추이 보조")

    if data_source_mode == "hybrid":
        videos_out = dedupe_concat_videos(csv_videos.copy(), api_videos)
        scoped = filter_metrics_by_dates(
            csv_metrics,
            pd.Timestamp(analysis_start_date),
            pd.Timestamp(analysis_end_date),
        )
        metrics_out = scoped.copy()
        metrics_out = overlay_series_by_date(metrics_out, nv_trend, "search_index")
        patch_cols = [
            "external_news_count",
            "external_blog_count",
            "external_cafe_count",
            "external_amplification_count",
        ]
        metrics_out = overlay_metrics_cols_from_daily(metrics_out, daily_ext, patch_cols)
        if not daily_ext.empty:
            nm = pd.to_numeric(metrics_out.get("external_news_count"), errors="coerce")
            metrics_out["news_count"] = nm
        metrics_out = overlay_multi_channel_cols(metrics_out, ch_df)
        metrics_out = overlay_youtube_aggregates(metrics_out, videos_out)

    elif strict:
        videos_out = api_videos.copy()
        metrics_out = _daily_metrics_nan_skeleton(analysis_start_date, analysis_end_date)
        metrics_out = overlay_series_by_date(metrics_out, nv_trend, "search_index")
        patch_cols = [
            "external_news_count",
            "external_blog_count",
            "external_cafe_count",
            "external_amplification_count",
        ]
        metrics_out = overlay_metrics_cols_from_daily(metrics_out, daily_ext, patch_cols)
        metrics_out = overlay_multi_channel_cols(metrics_out, ch_df)
        metrics_out = overlay_youtube_aggregates(metrics_out, videos_out)

    else:
        videos_out = api_videos if not api_videos.empty else yt.load_from_fallback_csv(
            creator_name, keywords, analysis_start_date, analysis_end_date
        )
        metrics_out = filter_metrics_by_dates(
            csv_metrics,
            pd.Timestamp(analysis_start_date),
            pd.Timestamp(analysis_end_date),
        )
        if metrics_out.empty:
            metrics_out = pd.DataFrame({
                "date": pd.date_range(
                    pd.Timestamp(analysis_start_date).normalize(),
                    pd.Timestamp(analysis_end_date).normalize(),
                    freq="D",
                )
            })
        metrics_out = overlay_series_by_date(metrics_out, nv_trend, "search_index")
        patch_cols = [
            "external_news_count",
            "external_blog_count",
            "external_cafe_count",
            "external_amplification_count",
        ]
        metrics_out = overlay_metrics_cols_from_daily(metrics_out, daily_ext, patch_cols)
        if not daily_ext.empty:
            nm = pd.to_numeric(metrics_out.get("external_news_count"), errors="coerce")
            metrics_out["news_count"] = nm
        metrics_out = overlay_multi_channel_cols(metrics_out, ch_df)
        metrics_out = overlay_youtube_aggregates(metrics_out, videos_out)

    miss_api: list[str] = []
    if strict:
        if api_videos.empty:
            miss_api.append("youtube_candidate_videos")
        if nv_trend.empty:
            miss_api.append("search_index(DataLab)")
        ext_series = metrics_out.get("external_amplification_count")
        if ext_series is None or pd.to_numeric(ext_series, errors="coerce").isna().all():
            miss_api.append("external_amplification_count")
        if ch_df.empty:
            miss_api.append("public_channel_analytics")
    resolver_meta["api_only_missing_features"] = miss_api

    fill_cand = np.nan if strict else 0.0
    for c in (
        "candidate_video_count",
        "candidate_video_total_views",
        "candidate_video_comment_count",
    ):
        if c not in metrics_out.columns:
            metrics_out[c] = fill_cand

    numeric_fill = [
        "search_index",
        "news_count",
        "external_amplification_count",
        "external_news_count",
        "external_blog_count",
        "external_cafe_count",
        "naver_news_count",
        "naver_blog_count",
        "naver_cafe_count",
        "creator_channel_daily_views",
        "creator_channel_subscriber_change",
    ]
    for nc in numeric_fill:
        if nc in metrics_out.columns:
            metrics_out[nc] = pd.to_numeric(metrics_out[nc], errors="coerce")

    metrics_out["candidate_video_count"] = pd.to_numeric(
        metrics_out["candidate_video_count"], errors="coerce"
    )
    metrics_out["candidate_video_total_views"] = pd.to_numeric(
        metrics_out["candidate_video_total_views"], errors="coerce"
    )
    metrics_out["candidate_video_comment_count"] = pd.to_numeric(
        metrics_out["candidate_video_comment_count"], errors="coerce"
    )
    if not strict:
        metrics_out["candidate_video_count"] = metrics_out["candidate_video_count"].fillna(0.0)
        metrics_out["candidate_video_total_views"] = metrics_out["candidate_video_total_views"].fillna(0.0)
        metrics_out["candidate_video_comment_count"] = metrics_out["candidate_video_comment_count"].fillna(
            0.0
        )

    metrics_out = canonicalize_external_amp_columns(
        metrics_out,
        allow_legacy_news_count=not strict,
        allow_breakdown_to_total=not strict,
    )
    return metrics_out, videos_out, notes, resolver_meta
