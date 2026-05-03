"""손해사정 검토 보조 마크다운 리포트 — LLM 2차 사용처(선택)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.creator_profile import CreatorProfile
from src.dri_calculator import trigger_level_from_dri
from src.llm_client import generate_adjuster_llm_summary

logger = logging.getLogger(__name__)

_REV_TYPE_KR = {
    "longform": "롱폼 조회 기반",
    "shorts": "숏츠",
    "sponsorship": "광고·협찬",
    "donation_membership": "후원·멤버십",
    "live": "라이브",
    "external": "외부 출연/행사",
}

_LOSS_AFFECTED_KR = {
    "advertising_sponsorship": "광고·협찬",
    "donation_membership": "후원·멤버십·라이브 성격",
    "platform_revenue": "플랫폼 조회수 기반 수익",
    "response_cost": "긴급대응·법무 등 비용",
}


class ReportGenerator:
    def generate_markdown(
        self,
        *,
        creator_name: str,
        period_label: str,
        dri_daily: pd.DataFrame,
        risky_videos: pd.DataFrame,
        kpis: dict[str, object],
        use_llm_summary: bool = False,
        data_source_mode: str = "csv_mock",
        creator_profile: CreatorProfile | None = None,
        loss_impact: object | None = None,
        applied_dri_weights: dict[str, float] | None = None,
        premium_proxy: dict[str, float] | None = None,
    ) -> str:
        case_name = kpis.get("case_name") or "-"
        event_date = kpis.get("event_date") or "-"
        last_dri = kpis.get("current_dri", "-")
        level = kpis.get("trigger_level", "-")
        peak_dri = kpis.get("peak_dri", "-")
        peak_date = kpis.get("peak_dri_date", "-")
        peak_lvl = kpis.get("peak_trigger_level", "-")
        d75 = kpis.get("days_above_75", "-")

        lines = [
            "# 안심 케어 보험 — 사이버렉카·허위정보 대응 사전 경보 및 손해사정 검토자료(MVP)",
            "",
            "**면책·기능 한계 안내.** 본 결과는 알고리즘에 따른 참고 신호입니다. 최종 보험금 지급 여부는 손해사정사 검토와 증빙 확인을 통해 결정합니다.",
            "",
            "## 1. 사건 개요",
            f"- 케이스명(선택): **{case_name}**",
            f"- 기준 이벤트일(선택): **{event_date}**",
            f"- 크리에이터(피모니터링 대상): **{creator_name}**",
            f"- 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 2. 크리에이터 프로필 및 보정 철학",
            "",
            "동일한 온라인 확산 규모라도 크리에이터의 수익구조와 대응역량에 따라 실제 손해 가능성은 달라진다. "
            "본 시스템은 크리에이터 프로필을 반영해 DRI를 보정하고, 손해사정사가 어떤 담보와 증빙을 우선 확인해야 하는지 제안한다.",
            "",
        ]

        if creator_profile is not None:
            mp = creator_profile.monetization.normalize()
            dm = creator_profile.dominant_revenue_type()
            dm_k = _REV_TYPE_KR.get(str(dm), str(dm))
            lines += [
                "### Creator Profile Summary",
                "",
                f"- 이름: **{creator_profile.creator_name}**",
                f"- 구독자 수: **{creator_profile.subscriber_count if creator_profile.subscriber_count is not None else '-'}**",
                f"- 평균 일별 조회수(표시값): **{creator_profile.avg_daily_views if creator_profile.avg_daily_views is not None else '-'}**",
                f"- 카테고리: **{creator_profile.content_category}**",
                f"- 플랫폼 집중도: **{creator_profile.platform_concentration_score:.2f}** · "
                f"콘텐츠 민감도: **{creator_profile.content_sensitivity_score:.2f}** · "
                f"대응 역량: **{creator_profile.response_capacity_score:.2f}**",
                f"- MCN 소속: **{creator_profile.mcn_affiliated}** · 법률/PR 지원: **{creator_profile.has_legal_pr_support}**",
                f"- **취약성 배수**(참조): **{creator_profile.vulnerability_multiplier():.3f}**",
                f"- **주요 수익 유형**(정규화 후): **{dm_k}** (`{dm}`)",
                "",
                "### Monetization Profile (규격화 후 비중)",
                "",
                "| 구분 | 비중 |",
                "|------|------|",
                f"| 롱폼 | {mp.longform_share:.3f} |",
                f"| 숏츠 | {mp.shorts_share:.3f} |",
                f"| 광고·협찬 | {mp.sponsorship_share:.3f} |",
                f"| 후원·멤버십 | {mp.donation_membership_share:.3f} |",
                f"| 라이브 | {mp.live_share:.3f} |",
                f"| 외부 | {mp.external_share:.3f} |",
                "",
            ]
        else:
            lines += [
                "- **프로필 보정 미적용**(고정 DRI 피처 가중치 · 취약성 배수 1.0).",
                "",
            ]

        lines += ReportGenerator._raw_vs_adjusted_block(kpis)

        if applied_dri_weights:
            lines += [
                "### 적용된 DRI 피처 가중치(합=1 재정규화 후)",
                "",
                "| 피처 | 가중치 |",
                "|------|------|",
            ]
            for key in sorted(applied_dri_weights.keys()):
                lines.append(f"| `{key}` | {applied_dri_weights[key]:.4f} |")
            lines.append("")

        if loss_impact is not None:
            aff = getattr(loss_impact, "affected_revenue_types", []) or []
            cov = getattr(loss_impact, "suggested_coverage", []) or []
            expl = getattr(loss_impact, "explanation", []) or []
            score = getattr(loss_impact, "revenue_impact_score", 0.0)
            lines += [
                "### Monetization Risk Interpretation · 손해 영향 가능 수익원(참고)",
                "",
                f"- 영향 신호 스코어(proxy): **{float(score):.3f}**",
                f"- 우선 검토 수익원: **{', '.join(_LOSS_AFFECTED_KR.get(a, a) for a in aff) or '-'}**",
                "- 제안 담보·검토:",
            ]
            for c in cov:
                lines.append(f"  - {c}")
            lines.append("- 해석:")
            for e in expl:
                lines.append(f"  - {e}")
            lines.append("")

        if premium_proxy:
            lines += [
                "### 상품 설계용 Premium Proxy(참고, 보험료 확정 아님)",
                "",
                f"- 순보험료 proxy: **{premium_proxy.get('pure_premium_proxy', 0):,.0f}** 원",
                f"- 모니터링비(상수): **{premium_proxy.get('monitoring_fee', 0):,.0f}** 원",
                f"- 클레임 처리비(상수): **{premium_proxy.get('claim_handling_cost', 0):,.0f}** 원",
                f"- 위험마진률: **{premium_proxy.get('risk_margin_rate', 0):.0%}**",
                f"- 연간 프리미엄 proxy: **{premium_proxy.get('annual_premium_proxy', 0):,.0f}** 원",
                "",
            ]

        lines += [
            "## 3. 모니터링 기간",
            period_label,
            "",
            "## 4. DRI 요약",
            f"- 종료 시점 DRI(**Creator-adjusted**, 참조): **{last_dri}** — 트리거: **{level}**",
            f"- 종료 시점 Raw DRI(참조): **{kpis.get('current_raw_dri', '-')}**",
            f"- **Peak DRI (adjusted)**: **{peak_dri}** (`{peak_date}`), 트리거: **{peak_lvl}**",
            f"- **Peak Raw DRI**: **{kpis.get('peak_raw_dri', '-')}** (`{kpis.get('peak_raw_dri_date', '-')}`)",
            f"- Creator 취약성 배수(기간 적용값): **{kpis.get('creator_vulnerability_multiplier', '-')}**",
            f"- DRI ≥ 75 지속 일수(adjusted 기준): **{d75}**",
            "",
            "| 지표 | 값 | 비고 |",
            "|------|-----|------|",
        ]

        def _cell(x: object) -> str:
            return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else str(x)

        metrics_rows = [
            ("후보 영상 수", kpis.get("candidate_videos_count", "-"), ""),
            ("후보 영상 총 조회수", kpis.get("total_views", "-"), ""),
            ("검색량 지수(최종일)", kpis.get("search_index_latest", "-"), "정량(샘플/CSV)"),
            ("기사 건수(최종일)", kpis.get("news_latest", "-"), "정량(샘플/CSV)"),
            ("DRI≥60 일수", _cell(kpis.get("days_above_60")), ""),
            ("DRI≥85 일수", _cell(kpis.get("days_above_85")), ""),
            ("표적화·문맥 점수 평균", _cell(kpis.get("mean_creator_targeting_context_score")), "LLM/룰 보조"),
            ("명예·사생활 노출 평균", _cell(kpis.get("mean_defamation_privacy_exposure_score")), "LLM/룰 보조"),
            ("콘텐츠 위험(블렌드) 평균", _cell(kpis.get("mean_content_risk_score")), ""),
            ("Toxicity 평균", _cell(kpis.get("mean_toxicity_score")), "키워드 mock 우선"),
            ("내러티브 중복 점수(일별 요약 평균)", _cell(kpis.get("mean_narrative_duplication_score")), "TF-IDF 군집"),
        ]

        for name, val, note in metrics_rows:
            lines.append(f"| {name} | {val} | {note} |")

        lines += [
            "",
            "## 5. 트리거 레벨 안내",
            "- DRI는 **보험금 자동 지급 기준이 아닙니다**. 내부 경보 및 **손해사정 검토 트리거**입니다.",
            "- 트리거 판단은 **Creator-adjusted DRI**(열 `dri`) 기준입니다.",
            "- 레벨: Normal / Level 1 / Level 2 / Level 3 (상세 구간은 UI/README 참조).",
            "",
            "## 6. 주요 이상징후",
        ]

        if dri_daily.empty or "dri" not in dri_daily.columns:
            lines.append("- 일별 데이터가 없거나 DRI 미산출 구간입니다.")
        else:
            try:
                dri_num = pd.to_numeric(dri_daily["dri"], errors="coerce")
                j = int(np.nanargmax(dri_num.to_numpy(dtype=float)))
                row = dri_daily.iloc[j]
                peak_d_raw = float(pd.to_numeric(row["dri"], errors="coerce"))
                lines.append(
                    f"- Adjusted DRI 피크일: `{row['date']}`, 값 **{peak_d_raw:.2f}** "
                    "(Raw 피크는 KPI **Peak Raw DRI** 참조)."
                )
            except Exception as e:
                logger.debug("Peak block skipped: %s", e)
                lines.append("- DRI 피크 산출에 필요한 정보가 부족합니다.")

        cols_hint = []
        if "candidate_video_count" in dri_daily.columns:
            cols_hint.append("candidate_video_count")
        if "search_index" in dri_daily.columns:
            cols_hint.append("search_index")
        if cols_hint:
            lines.append(f"- 급증 점검 컬럼: {', '.join(cols_hint)}.")

        lines += ["", "## 7. 위험 후보 콘텐츠 Top 5"]

        if risky_videos.empty:
            lines.append("- 후보 영상이 없거나 필터 결과가 비었습니다.")
        else:
            key = (
                "content_risk_score"
                if "content_risk_score" in risky_videos.columns
                else "candidate_priority_score"
            )

            top5 = risky_videos.copy()
            if key in top5.columns:
                top5 = top5.sort_values(by=key, ascending=False, na_position="last").head(5)
            else:
                top5 = top5.head(5)

            for _, vr in top5.iterrows():
                t = vr.get("title", "")
                url = vr.get("url", "")
                cr = vr.get("content_risk_score", vr.get(key, "-"))
                dp = vr.get("defamation_privacy_exposure_score", "-")
                tx = vr.get("toxicity_score", "-")
                lines.append(
                    f"- **{t}** — 콘텐츠위험(블렌드) {_cell(cr)}, 명예·사생활노출 {_cell(dp)}, Toxicity {_cell(tx)} — `{url}`"
                )

        lines += ["", "## 8. AI 판단 요약 (LLM, 선택적)"]

        lm_txt: str | None = None
        if use_llm_summary:
            brief = ReportGenerator._brief_for_adjuster_llm(
                creator_name=creator_name,
                period_label=period_label,
                kpis=kpis,
                dri_daily=dri_daily,
                data_source_mode=data_source_mode,
            )
            lm_txt = generate_adjuster_llm_summary(brief)

        if lm_txt:
            lines.append("")
            lines.append(str(lm_txt))
        else:
            lines.append("")
            lines.append("- (LLM 요약 미사용: OpenAI 미설정, 옵션 끔, 또는 호출 실패 시 템플릿 요약 아래 참고)")
            lines.append("- 상위 신호 요약:")
            lines.append(
                "  - OpenAI 설정 시 **표적화·문맥** 상위 후보만 LLM 검토 가능(비용 통제)."
            )
            lines.append("  - Toxicity(mock 키워드)·내러티브 중복은 룰/로컬 NLP.")

        lines += [
            "",
            "## 9. 보조 신호(LLM/mock·NLP) 요약 (참조)",
            "- 표적화·문맥 신호와 명예·사생활 노출 신호는 **참고용**입니다(법적 단정 불가).",
            "- Toxicity는 키워드 기반 mock에 가깝습니다(향후 HF 모델 교체 가능).",
            "- 내러티브 중복은 TF-IDF 유사 군집 기반 신호입니다(샘플 부족 시 미산출).",
            "",
            "## 10. 손해사정사 검토 필요 항목",
            "- 외부 콘텐츠 허위·협박·사생활 침해 해당성 **사실관계 확인**",
            "- 피해 규모(확산, 수익·구독 변동) 증적 및 **인과** 검토",
            "- 약관·면책·고지(가입 전 알려진 사실) 확인",
            "",
            "## 11. 손해사정사 확인 필요 증빙(체크리스트)",
            "- 원본 URL 및 **타임스탬프 포함 캡처** 보관",
            "- 게시/수집 시각 로그 및 체인 보전",
            "- 댓글·커뮤니티 **대표 문구 샘플** 확보",
            "- 검색량·언론량 변동 자료(Naver/Datalab 등 가능 시)",
            "- 플랫폼 **신고/삭제 요청** 내역",
            "- 법률·PR·포렌식 등 **비용 영수증**",
            "- **YouTube Analytics** 또는 플랫폼 **정산·RPM·수익** 변동 내역",
            "- **광고·협찬 계약서** 및 브랜드 세이프티 관련 **계약 변경·중단** 공문",
            "- **후원·멤버십·슈퍼챗(라이브 후원)** 내역 및 이탈 추이",
            "- **MCN 계약** 유무 및 대응 역할 분담",
            "- **법률/PR** 대응 가능 여부 및 비용 구조",
            "- 광고·협찬 **계약 취소** 등 수익 영향 증빙",
            "",
            "## 12. 권고 조치",
            "- 증거 보전, 내부 커뮤니케이션, 법무/PR 대응 시나리오 마련",
            "",
            "## 13. 면책·한계 검토 포인트",
            "- 정당한 비판/공공 이슈 논평 가능성 분리 검토",
            "- 피보험자 본인 귀책(선행 발언 등)",
            "- 가입 전 진행 중이던 분쟁/논란 여부",
            "- 단순 조회 순환 등 **비사건 요인**과의 분리",
            "",
            "---",
            "본 MVP는 규칙 기반 지표 및 제한적 LLM/룰+NLP 활용 결과입니다.",
            "**AI 생성 공격 탐지기가 아니라**, 평판·명예 피해 **모니터링·분류 신호 및 리포트 자동 초안**입니다.",
            "**AI는 보험금 자동 결정을 하지 않습니다.** 최종 지급은 손해사정사 검토·증빙 확인으로 이루어집니다.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _raw_vs_adjusted_block(kpis: dict[str, object]) -> list[str]:
        return [
            "### Raw DRI vs Creator-adjusted DRI",
            "",
            "- **Raw DRI**: 베이스라인 대비 온라인 확산 신호를 결합한 강도(0~100). 프로필 적용 시 피처 **가중치**가 조정될 수 있다.",
            "- **Adjusted DRI**: Raw에 **취약성 배수**를 곱한 값(상한 100). 프로필 미적용 시 Raw와 동일·배수 1.0.",
            f"- 본 기간 표시 Peak Raw / Peak Adjusted: **{kpis.get('peak_raw_dri', '-')}** / **{kpis.get('peak_dri', '-')}**",
            "",
        ]

    @staticmethod
    def _brief_for_adjuster_llm(
        *,
        creator_name: str,
        period_label: str,
        kpis: dict[str, object],
        dri_daily: pd.DataFrame,
        data_source_mode: str,
    ) -> str:
        tail = ""
        if not dri_daily.empty and "dri" in dri_daily.columns:
            try:
                cols = ["date", "raw_dri", "dri", "trigger_level"] if "raw_dri" in dri_daily.columns else ["date", "dri", "trigger_level"]
                t = dri_daily[[c for c in cols if c in dri_daily.columns]].tail(5)
                tail = t.to_string(index=False)
            except Exception:
                tail = ""
        lines = [
            f"피모니터링 대상: {creator_name}",
            f"기간: {period_label}",
            f"데이터 소스 모드: {data_source_mode}",
            "핵심 KPI (문자열):",
            repr({k: kpis.get(k) for k in sorted(kpis) if not str(k).startswith("_")})[:8000],
        ]
        if tail:
            lines.append("최근 5행 DRI 스냅샷:")
            lines.append(tail[:4000])
        return "\n".join(lines)

    def save_report(
        self,
        *,
        markdown: str,
        reports_dir: Path,
        basename: str = "damage_report",
    ) -> Path:
        reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = reports_dir / f"{basename}_{ts}.md"
        path.write_text(markdown, encoding="utf-8")
        return path


def build_kpis(
    *,
    creator_name: str,
    classified_videos: pd.DataFrame,
    dri_daily: pd.DataFrame,
    case_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    k: dict[str, object] = {"creator_name": creator_name}

    meta = case_meta or {}
    for mk in ("case_name", "event_date"):
        if mk in meta:
            k[mk] = meta[mk]

    try:
        if not dri_daily.empty and "dri" in dri_daily.columns:
            valid = dri_daily.dropna(subset=["dri"]).copy()
            valid["_d"] = pd.to_numeric(valid["dri"], errors="coerce")
            valid = valid.dropna(subset=["_d"])
            if not valid.empty:
                last_row = valid.iloc[-1]
                v_last = float(last_row["_d"])
                k["current_dri"] = v_last
                k["trigger_level"] = trigger_level_from_dri(v_last)

                j = int(valid["_d"].to_numpy(dtype=float).argmax())
                pr = valid.iloc[j]
                v_peak = float(pr["_d"])
                k["peak_dri"] = v_peak
                k["peak_dri_date"] = pr["date"]
                k["peak_trigger_level"] = trigger_level_from_dri(v_peak)

                dnum = pd.to_numeric(dri_daily["dri"], errors="coerce")
                k["days_above_60"] = int((dnum >= 60).sum())
                k["days_above_75"] = int((dnum >= 75).sum())
                k["days_above_85"] = int((dnum >= 85).sum())

                if "raw_dri" in dri_daily.columns:
                    vr = dri_daily.dropna(subset=["raw_dri"]).copy()
                    vr["_r"] = pd.to_numeric(vr["raw_dri"], errors="coerce")
                    vr = vr.dropna(subset=["_r"])
                    if not vr.empty:
                        k["current_raw_dri"] = round(float(vr["_r"].iloc[-1]), 2)
                        jr = int(vr["_r"].to_numpy(dtype=float).argmax())
                        k["peak_raw_dri"] = round(float(vr.iloc[jr]["_r"]), 2)
                        k["peak_raw_dri_date"] = vr.iloc[jr]["date"]

                if "creator_vulnerability_multiplier" in dri_daily.columns:
                    mvser = pd.to_numeric(dri_daily["creator_vulnerability_multiplier"], errors="coerce").dropna()
                    if not mvser.empty:
                        k["creator_vulnerability_multiplier"] = round(float(mvser.iloc[-1]), 4)
                if "dominant_revenue_type" in dri_daily.columns:
                    dr_last = dri_daily["dominant_revenue_type"].iloc[-1]
                    k["dominant_revenue_type"] = "-" if dr_last is None or str(dr_last) == "nan" else str(dr_last)
                if "profile_adjusted" in dri_daily.columns:
                    pa = dri_daily["profile_adjusted"].iloc[-1]
                    try:
                        k["profile_adjusted"] = bool(pa)
                    except (TypeError, ValueError):
                        k["profile_adjusted"] = False
            else:
                k["current_dri"] = "-"
                k["trigger_level"] = "Unknown"
                k["peak_dri"] = "-"
                k["peak_dri_date"] = "-"
                k["peak_trigger_level"] = "-"
                k["days_above_60"] = 0
                k["days_above_75"] = 0
                k["days_above_85"] = 0
        else:
            k["current_dri"] = "-"
            k["trigger_level"] = "-"
            k["peak_dri"] = "-"
            k["peak_dri_date"] = "-"
            k["peak_trigger_level"] = "-"
            k["days_above_60"] = 0
            k["days_above_75"] = 0
            k["days_above_85"] = 0
    except Exception as e:
        logger.debug("DRI KPI build failed: %s", e)

    if classified_videos.empty:
        k["candidate_videos_count"] = 0
        k["total_views"] = 0
        for key in (
            "mean_creator_targeting_context_score",
            "mean_defamation_privacy_exposure_score",
            "mean_content_risk_score",
            "mean_toxicity_score",
            "mean_narrative_duplication_score",
        ):
            k[key] = "-"
    else:
        k["candidate_videos_count"] = int(len(classified_videos))
        if "view_count" in classified_videos.columns:
            tv = pd.to_numeric(classified_videos["view_count"], errors="coerce").fillna(0).sum()
            k["total_views"] = float(tv)
        else:
            k["total_views"] = "-"

        def _mean(col: str) -> object:
            s = classified_videos.get(col)
            if s is None:
                return "-"
            a = pd.to_numeric(s, errors="coerce").dropna()
            return float(a.mean()) if not a.empty else "-"

        k["mean_creator_targeting_context_score"] = _mean("creator_targeting_context_score")
        k["mean_defamation_privacy_exposure_score"] = _mean("defamation_privacy_exposure_score")
        k["mean_content_risk_score"] = _mean("content_risk_score")
        k["mean_toxicity_score"] = _mean("toxicity_score")
        k["mean_narrative_duplication_score"] = _mean("narrative_duplication_score")

    if not dri_daily.empty:
        tail = dri_daily.iloc[-1]
        if "search_index" in dri_daily.columns:
            k["search_index_latest"] = tail.get("search_index", "-")
        if "news_count" in dri_daily.columns:
            k["news_latest"] = tail.get("news_count", "-")

    return k
