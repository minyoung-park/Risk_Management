"""csv_mock | live_api | hybrid 데이터 소스 조합 및 collector 호출."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.collectors.bigkinds_collector import BigKindsCollector
from src.collectors.naver_datalab_collector import NaverDataLabCollector
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
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    notes: list[str] = []

    csv_metrics = load_daily_metrics(metrics_csv_path)
    csv_videos = load_candidate_videos(videos_csv_path)

    if data_source_mode == "csv_mock":
        return csv_metrics.copy(), csv_videos.copy(), notes

    yt = YouTubeCollector(fallback_videos_csv=videos_csv_path)
    naver = NaverDataLabCollector(sample_daily_csv=metrics_csv_path)
    bk = BigKindsCollector(sample_daily_csv=metrics_csv_path)

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
    )

    api_videos = yt.search_via_api(creator_name, keywords, analysis_start_date, analysis_end_date)

    kg = []
    if keywords:
        kg.append([keywords[0][:30]])
        rest = keywords[1:4]
        for r in rest:
            if r.strip():
                kg.append([r.strip()[:30]])
    if not kg:
        kg = [[creator_name[:30] or "검색"]]

    nv_trend = naver.fetch_search_trend(kg, analysis_start_date, analysis_end_date)

    news_df = bk.fetch_news_count(
        creator_name,
        keywords,
        analysis_start_date,
        analysis_end_date,
    )

    ch_df = pch.fetch_public_channel_metrics(channel_url, analysis_start_date, analysis_end_date)

    if api_videos.empty:
        notes.append(
            "YouTube Data API 결과 없음 — 키·쿼터·키워드를 확인하세요. 후보 영상 CSV를 사용합니다."
        )
        api_part = yt.load_from_fallback_csv(
            creator_name, keywords, analysis_start_date, analysis_end_date
        )
    else:
        notes.append(f"YouTube API 후보 {len(api_videos)}건 로드.")

    if get_naver_configured():
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
        metrics_out = overlay_series_by_date(metrics_out, news_df, "news_count")
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
        metrics_out = overlay_series_by_date(metrics_out, news_df, "news_count")
        metrics_out = overlay_multi_channel_cols(metrics_out, ch_df)
        metrics_out = overlay_youtube_aggregates(metrics_out, videos_out)

    for c in [
        "candidate_video_count",
        "candidate_video_total_views",
        "candidate_video_comment_count",
    ]:
        if c not in metrics_out.columns:
            metrics_out[c] = 0.0

    numeric_fill = ["search_index", "news_count", "creator_channel_daily_views", "creator_channel_subscriber_change"]
    for nc in numeric_fill:
        if nc in metrics_out.columns:
            metrics_out[nc] = pd.to_numeric(metrics_out[nc], errors="coerce")

    metrics_out["candidate_video_count"] = pd.to_numeric(
        metrics_out["candidate_video_count"], errors="coerce"
    ).fillna(0.0)
    metrics_out["candidate_video_total_views"] = pd.to_numeric(
        metrics_out["candidate_video_total_views"], errors="coerce"
    ).fillna(0.0)
    metrics_out["candidate_video_comment_count"] = pd.to_numeric(
        metrics_out["candidate_video_comment_count"], errors="coerce"
    ).fillna(0.0)

    return metrics_out, videos_out, notes
