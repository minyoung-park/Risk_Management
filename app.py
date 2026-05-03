"""
Creator Shield AI — 온라인 명예·평판 위협 모니터링 MVP 대시보드.

본 앱은 “AI 생성 공격 탐지기”가 아니라 렉카·허위정보·악성 댓글 등 **평판·명예 피해 신호**를
모니터링하고 손해사정 검토를 돕기 위한 참고용 프로토타입입니다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.ai_classifier import AIContentRiskClassifier, aggregate_nlp_daily
from src.config import DATA_DIR, REPORTS_DIR
from src.creator_profile import CreatorProfile, MonetizationProfile, monetization_share_dict
from src.data_loader import (
    CREATOR_T_CANDIDATE_VIDEOS_CSV,
    CREATOR_T_DAILY_METRICS_CSV,
    DEFAULT_CANDIDATE_VIDEOS_CSV,
    DEFAULT_DAILY_METRICS_CSV,
    SAMPLE_CHANNEL_ANALYTICS_MANUAL_CSV,
    SAMPLE_CREATOR_PROFILES_CSV,
    filter_metrics_by_dates,
    filter_videos_by_dates,
    load_daily_metrics,
)
from src.data_sources import resolve_metrics_and_videos
from src.dri_calculator import DRICalculator, build_baseline, resolved_weights_for_profile
from src.loss_impact import estimate_loss_impact
from src.premium_proxy import estimate_premium_proxy
from src.profile_loader import default_creator_profile, resolve_profile_from_csv
from src.report_generator import ReportGenerator, build_kpis


def _parse_keywords(txt: str) -> list[str]:
    return [k.strip() for k in (txt or "").split(",") if k.strip()]


def _apply_keyword_filter(videos_df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    if videos_df.empty or not keywords:
        return videos_df
    if not {"title", "description"}.issubset(videos_df.columns):
        return videos_df
    blob = videos_df["title"].fillna("") + " " + videos_df["description"].fillna("")

    def row_match(s: str) -> bool:
        low = str(s).lower()
        return any(k.lower() in low for k in keywords)

    return videos_df[blob.apply(row_match)].reset_index(drop=True)


def _baseline_for_mock_demo(full_metrics: pd.DataFrame, analysis_start_dt: pd.Timestamp) -> pd.DataFrame:
    """분석 시작일 이전 30일(가능하면) 구간으로 베이스라인을 자동 설정."""
    fm = full_metrics.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if fm.empty:
        return fm

    cutoff = pd.Timestamp(analysis_start_dt).normalize()
    pre = fm[fm["date"] < cutoff]
    if pre.empty:
        span = max(14, min(21, len(fm) // 3))
        return fm.iloc[:span].copy()

    b_end = cutoff - timedelta(days=1)
    b_start = cutoff - timedelta(days=30)
    win = filter_metrics_by_dates(pre, pd.Timestamp(b_start), pd.Timestamp(b_end))
    if win.empty:
        span = max(14, min(21, len(pre)))
        return pre.iloc[-span:].copy()
    return win


def main() -> None:
    st.set_page_config(
        page_title="Creator Shield AI (MVP)",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Creator Shield AI — 명예·평판 피해 모니터링 (MVP)")

    st.info(
        "**이 시스템은 AI ‘생성 공격’ 탐지기가 아닙니다.** 온라인 명예·사이버렉카형 평판 피해 **신호 추정** 및 "
        "손해사정 검토 **리포트 자동 초안**을 목표로 합니다. "
        "DRI는 **보험금 자동 지급 또는 자동 책임 결정 기준이 아니며**, **내부 경보 및 손해사정 검토 트리거**입니다."
    )

    default_kw_demo = "논란, 폭로, 협박, 해명, 사기, 거짓말, 뒷광고, 렉카, 녹취, 사생활"
    default_kw_case = "협박, 해명, 녹취, 사생활, 렉카, 폭로, 공갈, 논란"

    incident_probability = 0.05
    expected_response_cost = 2_500_000.0

    preset_metrics = {
        "표준 샘플 일별 지표 (Creator A)": DEFAULT_DAILY_METRICS_CSV,
        "사례형 샘플 일별 지표 (Creator T)": CREATOR_T_DAILY_METRICS_CSV,
    }
    preset_videos = {
        "표준 샘플 후보 영상 (Creator A)": DEFAULT_CANDIDATE_VIDEOS_CSV,
        "사례형 샘플 후보 영상 (Creator T)": CREATOR_T_CANDIDATE_VIDEOS_CSV,
    }

    with st.sidebar:
        st.header("케이스 모드")
        case_mode = st.radio(
            "case_mode",
            options=["mock_demo", "historical_case"],
            format_func=lambda x: "실시간형 데모(mock_demo)"
            if x == "mock_demo"
            else "사후 사례 재현(historical_case)",
        )

        st.divider()
        st.subheader("데이터 소스")
        data_source_mode = st.radio(
            "data_source_mode",
            options=["csv_mock", "live_api", "hybrid"],
            format_func=lambda x: {
                "csv_mock": "csv_mock · CSV/mock만",
                "live_api": "live_api · API 우선(+CSV 폴백)",
                "hybrid": "hybrid · CSV+API 병합",
            }[x],
            help=(
                "YouTube·Naver 키가 있으면 후보 영상·검색추이를 불러오고, "
                "BigKinds·SocialBlade·Vling 자동 수집은 미연동입니다(향후 또는 수동 CSV)."
            ),
            index=0,
        )

        channel_url_input = st.text_input(
            "channel_url (YouTube 등, 채널 지표 참고)",
            value="https://www.youtube.com/@creator_a_demo",
        )

        analytics_csv_label = None
        analytics_provider_pick = "manual_csv"
        if data_source_mode != "csv_mock":
            analytics_pick = st.selectbox(
                "채널·수익 수동 메트릭 CSV (예: Vling 내보내기)",
                options=["미사용", "샘플: Vling 수동 자리표시자"],
            )
            analytics_csv_label = SAMPLE_CHANNEL_ANALYTICS_MANUAL_CSV if analytics_pick.startswith("샘플") else None
            analytics_provider_pick = st.selectbox(
                "provider (실제 호출 미구현 시 CSV 폴백)",
                ["manual_csv", "vling", "socialblade", "playboard"],
                index=0,
            )

        st.divider()

        metrics_label = st.selectbox("daily_metrics 파일", options=list(preset_metrics.keys()))
        videos_label = st.selectbox("candidate_videos 파일", options=list(preset_videos.keys()))
        metrics_path = preset_metrics[metrics_label]
        videos_path = preset_videos[videos_label]

        use_mock_llm = st.toggle("Mock LLM/룰 강제(비용 없음)", value=True)

        llm_adjuster_summary_in_md = st.toggle(
            "리포트에 ‘AI 판단 요약’ LLM 블록 포함(OpenAI 필요)",
            value=False,
            help="요약 소절만 API 호출합니다. 무분별 사용은 비용·시간 증가.",
        )

        if case_mode == "historical_case":
            case_name = st.text_input("case_name", value="Creator T reputational spike (sample)")
            event_date = st.date_input("event_date (표시용)", value=date(2025, 3, 10))
            baseline_start_date = st.date_input("baseline_start_date", value=date(2025, 3, 1))
            baseline_end_date = st.date_input("baseline_end_date", value=date(2025, 3, 8))
            analysis_start_date = st.date_input("analysis_start_date", value=date(2025, 3, 1))
            analysis_end_date = st.date_input("analysis_end_date", value=date(2025, 3, 25))
            creator_name = st.text_input("creator_name", value="Creator T")
            kw_default = default_kw_case
            auto_baseline = False

        else:
            case_name = st.text_input("case_name (선택)", value="Sandbox demo")
            event_date = st.date_input("event_date (선택/표시용)", value=date(2024, 6, 15))
            analysis_start_date = st.date_input("analysis_start_date", value=date(2024, 6, 1))
            analysis_end_date = st.date_input("analysis_end_date", value=date(2024, 7, 31))
            baseline_start_date = baseline_end_date = analysis_start_date
            creator_name = st.text_input("creator_name", value="Creator A")
            kw_default = default_kw_demo
            auto_baseline = st.toggle(
                "베이스라인 자동(분석 시작 이전 최대 30일)",
                value=True,
                help="historical_case는 위 baseline_start/end 입력을 사용합니다.",
            )
            if not auto_baseline:
                baseline_start_date = st.date_input("baseline_start_date (수동)", value=analysis_start_date)
                baseline_end_date = st.date_input("baseline_end_date (수동)", value=analysis_start_date)

        monitoring_keywords = st.text_area(
            "monitoring_keywords (쉼표 구분)", value=kw_default, height=90
        )
        st.caption(
            "**선택 확장 위험 유형**(키워드에 추가 가능): 예) 딥페이크, 가짜 보도, 조작 의혹 — 기본 과제에서는 중심 키워드에서 과도 노출하지 않습니다."
        )

        st.divider()
        st.subheader("Creator Profile / Monetization")
        apply_profile_layer = st.toggle(
            "크리에이터 프로필로 가중치·취약성 보정",
            value=True,
            help="끄면 고정 DRI 피처 가중치·취약성 배수 1.0(레거시와 동등).",
        )
        use_prof_csv = True
        profile_choice = "Creator A"
        manual_mode = False
        pc_label = creator_name or ""
        sub_count_m = 300000
        avg_daily_views_m = 120000
        avg_daily_comments_m = 1500
        content_cat_m = "general"
        share_lf, share_sh, share_sp = 0.55, 0.2, 0.15
        share_dm, share_lv, share_ex = 0.05, 0.03, 0.02
        platform_conc_m = 0.7
        content_sens_m = 0.4
        face_voice_m = 0.6
        fan_dep_m = 0.5
        past_attack_m = 0.2
        response_cap_m = 0.35
        mcn_m = False
        legal_m = False

        if apply_profile_layer:
            use_prof_csv = st.toggle("프로필 CSV 사용", value=True)
            if use_prof_csv:
                profile_choice = st.selectbox(
                    "creator_profile",
                    ["Creator T", "Creator A", "직접 입력"],
                )
            else:
                profile_choice = "직접 입력"
            manual_mode = (profile_choice == "직접 입력") or (not use_prof_csv)

            if manual_mode:
                pc_label = st.text_input("직접 프로필 이름", value=creator_name or "내 채널")
                sub_count_m = int(
                    st.number_input(
                        "구독자 수",
                        min_value=0,
                        max_value=200_000_000,
                        value=max(1000, int(sub_count_m)),
                        step=5000,
                    )
                )
                avg_daily_views_m = float(
                    st.number_input(
                        "평균 일별 조회수(참고)",
                        min_value=0.0,
                        max_value=50_000_000.0,
                        value=float(avg_daily_views_m),
                        step=1000.0,
                    )
                )
                avg_daily_comments_m = float(
                    st.number_input(
                        "평균 일별 댓글 수(참고)",
                        min_value=0.0,
                        max_value=10_000_000.0,
                        value=float(avg_daily_comments_m),
                        step=100.0,
                    )
                )
                content_cat_m = st.text_input("콘텐츠 카테고리", value=content_cat_m)
                share_lf = float(st.slider("롱폼 수익 비중", 0.0, 1.0, float(share_lf), 0.01))
                share_sh = float(st.slider("숏츠 수익 비중", 0.0, 1.0, float(share_sh), 0.01))
                share_sp = float(st.slider("광고·협찬 비중", 0.0, 1.0, float(share_sp), 0.01))
                share_dm = float(st.slider("후원·멤버십 비중", 0.0, 1.0, float(share_dm), 0.01))
                share_lv = float(st.slider("라이브 비중", 0.0, 1.0, float(share_lv), 0.01))
                share_ex = float(st.slider("외부 출연/행사 비중", 0.0, 1.0, float(share_ex), 0.01))
                platform_conc_m = float(st.slider("플랫폼 집중도", 0.0, 1.0, float(platform_conc_m)))
                content_sens_m = float(st.slider("콘텐츠 민감도", 0.0, 1.0, float(content_sens_m)))
                face_voice_m = float(st.slider("얼굴·목소리 노출", 0.0, 1.0, float(face_voice_m)))
                fan_dep_m = float(st.slider("팬덤·커뮤니티 의존도", 0.0, 1.0, float(fan_dep_m)))
                past_attack_m = float(st.slider("과거 공격·논란 노출 체감", 0.0, 1.0, float(past_attack_m)))
                response_cap_m = float(st.slider("대응 역량", 0.0, 1.0, float(response_cap_m)))
                mcn_m = st.checkbox("MCN 소속", value=mcn_m)
                legal_m = st.checkbox("법률·PR 체계적 지원", value=legal_m)

            if use_prof_csv and profile_choice in ("Creator T", "Creator A"):
                st.caption(f"프로필 파일: `{SAMPLE_CREATOR_PROFILES_CSV.name}`")

            with st.expander("Premium proxy (참고, 확정료 아님)", expanded=False):
                incident_probability = float(
                    st.slider("사건 발생 경향 proxy", 0.0, 0.5, float(incident_probability), 0.01)
                )
                expected_response_cost = float(
                    st.number_input(
                        "기대 1건 긴급대응·법무 비용 proxy(원)",
                        min_value=0,
                        max_value=200_000_000,
                        value=int(expected_response_cost),
                        step=50_000,
                    )
                )

    creator_profile_ctx: CreatorProfile | None = None
    if apply_profile_layer:
        if use_prof_csv and profile_choice in ("Creator T", "Creator A"):
            creator_profile_ctx = resolve_profile_from_csv(
                SAMPLE_CREATOR_PROFILES_CSV, profile_choice
            )
            if creator_profile_ctx is None:
                creator_profile_ctx = default_creator_profile(profile_choice)
        elif manual_mode:
            creator_profile_ctx = CreatorProfile(
                creator_name=str(pc_label).strip() or str(creator_name).strip() or "unknown",
                subscriber_count=sub_count_m,
                avg_daily_views=avg_daily_views_m,
                avg_daily_comments=avg_daily_comments_m,
                content_category=str(content_cat_m).strip() or "general",
                monetization=MonetizationProfile(
                    longform_share=share_lf,
                    shorts_share=share_sh,
                    sponsorship_share=share_sp,
                    donation_membership_share=share_dm,
                    live_share=share_lv,
                    external_share=share_ex,
                ),
                platform_concentration_score=platform_conc_m,
                content_sensitivity_score=content_sens_m,
                face_voice_exposure_score=face_voice_m,
                fan_community_dependency_score=fan_dep_m,
                past_attack_history_score=past_attack_m,
                response_capacity_score=response_cap_m,
                mcn_affiliated=mcn_m,
                has_legal_pr_support=legal_m,
            )

    try:
        csv_snapshot_metrics = load_daily_metrics(metrics_path)
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    start_dt = pd.Timestamp(analysis_start_date)
    end_dt = pd.Timestamp(analysis_end_date)
    keywords = _parse_keywords(monitoring_keywords)

    if start_dt > end_dt:
        st.warning("분석 시작일이 종료일보다 늦었습니다 — 값을 교환합니다.")
        start_dt, end_dt = end_dt, start_dt

    if case_mode == "historical_case":
        bs = pd.Timestamp(baseline_start_date)
        be = pd.Timestamp(baseline_end_date)
        if bs > be:
            st.warning("베이스라인 시작/종료를 교환합니다.")
            bs, be = be, bs
        baseline_metrics = filter_metrics_by_dates(csv_snapshot_metrics, bs, be)
    else:
        if auto_baseline:
            baseline_metrics = _baseline_for_mock_demo(csv_snapshot_metrics, start_dt)
        else:
            bs = pd.Timestamp(baseline_start_date)
            be = pd.Timestamp(baseline_end_date)
            if bs > be:
                bs, be = be, bs
            baseline_metrics = filter_metrics_by_dates(csv_snapshot_metrics, bs, be)

    if baseline_metrics.empty or len(baseline_metrics) < 2:
        st.error("베이스라인 구간 데이터가 너무 짧거나 비었습니다. 날짜/파일 선택을 확인하세요.")
        st.stop()

    try:
        full_metrics, full_videos, intake_notes = resolve_metrics_and_videos(
            data_source_mode=data_source_mode,
            metrics_csv_path=metrics_path,
            videos_csv_path=videos_path,
            creator_name=creator_name,
            keywords=keywords,
            analysis_start_date=analysis_start_date,
            analysis_end_date=analysis_end_date,
            channel_url=channel_url_input.strip(),
            analytics_manual_csv_path=analytics_csv_label,
            analytics_provider=analytics_provider_pick,
        )
    except Exception as e:
        st.error(f"데이터 소스 처리 실패: {e}")
        st.stop()

    for note in intake_notes:
        st.sidebar.caption(note)

    subset_videos = filter_videos_by_dates(full_videos, start_dt, end_dt)
    subset_videos = _apply_keyword_filter(subset_videos, keywords)
    subset_metrics = filter_metrics_by_dates(full_metrics.copy(), start_dt, end_dt)

    baseline = build_baseline(baseline_metrics)

    with st.spinner("콘텐츠 신호 처리 중(Mock/LLM+NLP 상위 우선 처리)…"):
        classifier = AIContentRiskClassifier(force_mock=use_mock_llm, max_llm_items=10)
        classified_videos = classifier.classify_dataframe(creator_name, subset_videos)

    tox_daily, nar_daily, tgt_daily = aggregate_nlp_daily(classified_videos)

    calc = DRICalculator()
    dri_df = calc.compute_daily_dri(
        subset_metrics,
        toxicity_by_date=tox_daily,
        narrative_duplication_by_date=nar_daily,
        creator_targeting_by_date=tgt_daily,
        baseline=baseline,
        creator_profile=creator_profile_ctx,
    )

    case_meta = {
        "case_name": case_name,
        "event_date": str(event_date),
    }

    kpis = build_kpis(
        creator_name=creator_name,
        classified_videos=classified_videos,
        dri_daily=dri_df,
        case_meta=case_meta if case_name else None,
    )

    weights_applied = resolved_weights_for_profile(creator_profile_ctx)
    weights_baseline = resolved_weights_for_profile(None)
    loss_estimate = (
        estimate_loss_impact(creator_profile_ctx, kpis, dri_df)
        if creator_profile_ctx is not None
        else None
    )
    prem_dict = (
        estimate_premium_proxy(creator_profile_ctx, incident_probability, expected_response_cost)
        if creator_profile_ctx is not None
        else None
    )

    if case_mode == "historical_case":
        st.subheader("핵심 KPI (사후 사례: Peak 중심)")
        cpa, cpb, cpc = st.columns(3)
        cpa.metric("Peak Adjusted", f"{kpis.get('peak_dri', '-')}", help="취약성 배수 적용 후")
        cpb.metric("Peak 일자", f"{kpis.get('peak_dri_date', '-')}")
        cpc.metric("Peak 트리거", f"{kpis.get('peak_trigger_level', '-')}")
        cq1, cq2 = st.columns(2)
        cq1.metric("현재 Adjusted DRI", f"{kpis.get('current_dri', '-')}")
        cq2.metric("DRI≥75 지속 일수", f"{kpis.get('days_above_75', '-')}")
        cq3, cq4 = st.columns(2)
        cq3.metric("Peak Raw DRI", f"{kpis.get('peak_raw_dri', '-')}")
        cq4.metric("취약성 배수", f"{kpis.get('creator_vulnerability_multiplier', '-')}")
    else:
        st.subheader("핵심 KPI")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재 Adjusted DRI", f"{kpis.get('current_dri', '-')}")
        c2.metric("Peak Adjusted", f"{kpis.get('peak_dri', '-')}")
        c3.metric("Peak 트리거", f"{kpis.get('peak_trigger_level', '-')}")
        c4.metric("DRI≥75 일수", f"{kpis.get('days_above_75', '-')}")
        cw1, cw2 = st.columns(2)
        cw1.metric("Peak Raw DRI", f"{kpis.get('peak_raw_dri', '-')}")
        cw2.metric("취약성 배수", f"{kpis.get('creator_vulnerability_multiplier', '-')}")

    cols = st.columns(4)
    cols[0].metric("후보 영상 수", f"{kpis.get('candidate_videos_count', 0)}")
    cols[1].metric("후보 총 조회수", f"{kpis.get('total_views', 0)}")
    cols[2].metric("검색량 지수(최종일)", f"{kpis.get('search_index_latest', '-')}")
    cols[3].metric("기사 건수(최종일)", f"{kpis.get('news_latest', '-')}")

    cols2 = st.columns(4)
    cols2[0].metric(
        "표적화·문맥 신호 평균",
        f"{kpis.get('mean_creator_targeting_context_score', '-')}",
    )
    cols2[1].metric(
        "명예·사생활 노출 평균",
        f"{kpis.get('mean_defamation_privacy_exposure_score', '-')}",
    )
    cols2[2].metric(
        "Toxicity 평균(mock)",
        f"{kpis.get('mean_toxicity_score', '-')}",
    )
    cols2[3].metric(
        "내러티브 중복(일별) 평균",
        f"{kpis.get('mean_narrative_duplication_score', '-')}",
    )

    if creator_profile_ctx is not None:
        st.subheader("Creator Profile 요약")
        p1, p2, p3, p4 = st.columns(4)
        if creator_profile_ctx.subscriber_count is not None:
            p1.metric("구독자 수", f"{creator_profile_ctx.subscriber_count:,}")
        else:
            p1.metric("구독자 수", "-")
        p2.metric("취약성 배수", f"{creator_profile_ctx.vulnerability_multiplier():.4f}")
        dom = creator_profile_ctx.dominant_revenue_type()
        p3.metric("주요 수익 유형", dom)
        p4.metric("프로필 적용 여부", f"{kpis.get('profile_adjusted', '-')}")
        shar = monetization_share_dict(creator_profile_ctx.monetization)
        pie_df = pd.DataFrame({"label": list(shar.keys()), "비중": list(shar.values())})
        fig_pie = px.pie(pie_df, names="label", values="비중", title="수익구조 비중(정규화 후 참고)")
        st.plotly_chart(fig_pie, use_container_width=True)

        ww1, ww2 = st.columns(2)
        ww1.markdown("**기본 DRI 가중치(프로필 없음)**")
        ww1.dataframe(pd.DataFrame([weights_baseline]).T.rename(columns={0: "가중치"}), use_container_width=True)
        ww2.markdown("**적용된 DRI 가중치**")
        ww2.dataframe(pd.DataFrame([weights_applied]).T.rename(columns={0: "가중치"}), use_container_width=True)

        if loss_estimate is not None:
            st.markdown("##### 손해 영향 가능 수익원(참고)")
            st.write(
                f"- 영향 신호(proxy): `{loss_estimate.revenue_impact_score:.3f}`\n"
                f"- 검토 우선 유형: `{'`, `'.join(loss_estimate.affected_revenue_types)}`\n"
                f"- 해석:\n"
                + "\n".join(f"  - {e}" for e in loss_estimate.explanation)
            )

        if prem_dict is not None:
            with st.expander("Premium proxy (연간 참고값·확정료 아님)", expanded=False):
                st.json(prem_dict)
    elif not apply_profile_layer:
        st.caption(
            "**프로필 보정 미적용** 모드입니다. 고정 가중치·취약성 배수 1.0(Raw와 Adjusted DRI 동일)."
        )

    if not dri_df.empty and "date" in dri_df.columns:
        dd = dri_df.copy()
        if "raw_dri" in dd.columns:
            fig_dri = go.Figure()
            fig_dri.add_trace(
                go.Scatter(
                    x=dd["date"],
                    y=pd.to_numeric(dd["raw_dri"], errors="coerce"),
                    name="Raw DRI",
                    mode="lines+markers",
                )
            )
            fig_dri.add_trace(
                go.Scatter(
                    x=dd["date"],
                    y=pd.to_numeric(dd["dri"], errors="coerce"),
                    name="Adjusted DRI",
                    mode="lines+markers",
                )
            )
            fig_dri.update_layout(title="날짜별 Raw vs Adjusted DRI", hovermode="x unified")
            st.plotly_chart(fig_dri, use_container_width=True)
        else:
            fig_dri = px.line(dd, x="date", y="dri", title="날짜별 DRI", markers=True)
            st.plotly_chart(fig_dri, use_container_width=True)

        cols_for_mix = []
        if "candidate_video_count" in dd.columns:
            cols_for_mix.append("candidate_video_count")
        if "search_index" in dd.columns:
            cols_for_mix.append("search_index")
        if "news_count" in dd.columns:
            cols_for_mix.append("news_count")

        melt_src = dd[["date"] + [c for c in cols_for_mix if c in dd.columns]]
        if len(melt_src.columns) > 1:
            melt = melt_src.melt(id_vars=["date"], var_name="지표", value_name="값")
            fig_mx = px.line(melt, x="date", y="값", color="지표", title="후보·검색·기사 (날짜별)")
            st.plotly_chart(fig_mx, use_container_width=True)

        if {"date", "creator_channel_daily_views"}.issubset(dd.columns):
            fig_cb = px.line(
                dd,
                x="date",
                y="creator_channel_daily_views",
                title="크리에이터 채널 일일 조회수(샘플/CSV)",
                markers=True,
            )
            st.plotly_chart(fig_cb, use_container_width=True)

    st.subheader("후보 콘텐츠 테이블")

    def _thr(row: pd.Series) -> bool:
        try:
            cr = float(row.get("creator_targeting_context_score", np.nan))
            cb = float(row.get("content_risk_score", np.nan))
            return (np.isfinite(cr) and cr >= 0.35) or (np.isfinite(cb) and cb >= 0.35)
        except (TypeError, ValueError):
            return False

    if classified_videos.empty:
        st.caption("이 기간/키워드 결과가 비었습니다.")
    else:
        disp = classified_videos.copy()
        disp["trigger_related"] = disp.apply(_thr, axis=1)

        cols_show = [
            c
            for c in (
                "title",
                "url",
                "view_count",
                "comment_count",
                "candidate_priority_score",
                "content_risk_score",
                "defamation_privacy_exposure_score",
                "creator_targeting_context_score",
                "toxicity_score",
                "narrative_cluster_id",
                "narrative_duplication_score",
                "llm_context_review",
                "evidence_str",
                "trigger_related",
            )
            if c in disp.columns
        ]
        tbl = disp[cols_show].sort_values(
            by=("content_risk_score" if "content_risk_score" in disp.columns else "candidate_priority_score"),
            ascending=False,
            na_position="last",
        )
        tbl_fmt = tbl.copy()

        def _rnd4(x: object) -> object:
            try:
                xf = float(x)  # type: ignore[arg-type]
                return round(xf, 4) if np.isfinite(xf) else ""
            except (TypeError, ValueError):
                return x

        for nm in (
            "content_risk_score",
            "defamation_privacy_exposure_score",
            "creator_targeting_context_score",
            "toxicity_score",
            "narrative_duplication_score",
            "candidate_priority_score",
        ):
            if nm in tbl_fmt.columns:
                tbl_fmt[nm] = tbl_fmt[nm].apply(_rnd4)

        st.data_editor(
            tbl_fmt,
            use_container_width=True,
            hide_index=True,
            column_config={
                "title": st.column_config.TextColumn("제목"),
                "url": st.column_config.LinkColumn("URL"),
                "view_count": st.column_config.NumberColumn("조회수", format="%d"),
                "comment_count": st.column_config.NumberColumn("댓글 수", format="%d"),
                "candidate_priority_score": st.column_config.NumberColumn(
                    "우선순위(룰 기반)",
                    format="%.4f",
                ),
                "content_risk_score": st.column_config.NumberColumn(
                    "콘텐츠위험(블렌드)",
                    format="%.4f",
                ),
                "defamation_privacy_exposure_score": st.column_config.NumberColumn(
                    "명예·사생활노출",
                    format="%.4f",
                ),
                "creator_targeting_context_score": st.column_config.NumberColumn(
                    "표적화·문맥",
                    format="%.4f",
                ),
                "toxicity_score": st.column_config.NumberColumn("Toxicity(mock)", format="%.4f"),
                "narrative_cluster_id": st.column_config.NumberColumn("내러티브 클러스터"),
                "narrative_duplication_score": st.column_config.NumberColumn("내러티브 중복(일)", format="%.4f"),
                "llm_context_review": st.column_config.CheckboxColumn("LLM 우선 검토"),
                "evidence_str": st.column_config.TextColumn("증거 요약(evidence)", width="large"),
                "trigger_related": st.column_config.CheckboxColumn("트리거 연관"),
            },
            disabled=list(tbl_fmt.columns),
        )

    st.divider()
    st.subheader("손해사정 리포트 (.md 저장)")
    period_label = (
        f"{analysis_start_date.isoformat()} ~ {analysis_end_date.isoformat()} | "
        f"data_source={data_source_mode} | 지표파일 `{metrics_path.name}`"
    )
    use_llm_for_report = bool(llm_adjuster_summary_in_md)
    if st.button("리포트 생성 및 reports/ 에 저장"):
        rg = ReportGenerator()
        md = rg.generate_markdown(
            creator_name=creator_name,
            period_label=period_label,
            dri_daily=dri_df,
            risky_videos=classified_videos,
            kpis={**kpis, **case_meta},
            use_llm_summary=use_llm_for_report,
            data_source_mode=data_source_mode,
            creator_profile=creator_profile_ctx,
            loss_impact=loss_estimate,
            applied_dri_weights=weights_applied if creator_profile_ctx is not None else None,
            premium_proxy=prem_dict if prem_dict else None,
        )
        out_path = rg.save_report(markdown=md, reports_dir=REPORTS_DIR, basename="adjuster_review")
        st.success(f"저장 완료: `{out_path}`")

    with st.expander("데이터·운영 참고"):
        st.markdown(
            f"- **data_source_mode**: `{data_source_mode}` (csv_mock=CSV만, hybrid/live는 collector 호출 시도)\n"
            f"- 일별 지표 경로: `{metrics_path}` / 후보 영상: `{videos_path}`\n"
            f"- 스냅샷 샘플(향후 velocity): `{DATA_DIR / 'sample_video_snapshots.csv'}`\n"
            f"- 수동 채널·수익 proxy CSV 예시: `{SAMPLE_CHANNEL_ANALYTICS_MANUAL_CSV}`\n"
            "- **AI 사용 정리**: OpenAI 키 + Mock 끄면 상위 후보 문맥 분류에만 LLM 사용. "
            "Toxicity·내러티브·리포트 본문은 기본 룰/템플릿(요약 토글 시 LLM 소절 추가).\n"
            "- YouTube·Naver는 키가 있을 때만 실제 호출; BigKinds·Vling·SocialBlade **자동 API는 미구현**(CSV 보조)."
        )


if __name__ == "__main__":
    main()
