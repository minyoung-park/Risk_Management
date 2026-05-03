# Creator Shield AI (MVP)

보험·리스크 공모전용 **“온라인 명예훼손·사이버렉카형 평판 피해 모니터링”** 프로토타입입니다.

**이 시스템은 AI ‘생성 공격’ 탐지기가 아닙니다.** 게시물·영상·댓글·기사 등에서 **명예·평판·금전·정신 피해 가능성이 커지는 신호**를 모으고, 손해사정 검토용 **DRI·리포트 초안**을 만드는 참고용입니다.  
실제 지급·면책·법률 판정 기능은 **포함하지 않습니다**.

## 목적

- 일별 **정량 지표**(후보 영상 수·노출 규모 추정·댓글·검색·기사 등)를 **`baseline` 구간 평균/분산** 대비 z-score로 0~100에 매핑
- **표적화·문맥**(LLM/mock, 상위 우선), **Toxicity**(키워드 mock, HF 교체 TODO), **내러티브 중복**(TF-IDF 군집)으로 보조 피처 제공
- Peak DRI 등 **사후 사례(historical_case)** 분석에 맞춘 KPI 및 손해사정사 **증빙 체크리스트** 포함 리포트

**AI는 보험금 자동 결정을 하지 않습니다.** DRI는 **손해사정 검토 트리거**이며, 최종 판단은 사람·증빙을 전제로 합니다.

## Creator Profile과 AI·규칙 보정 목적 요약

유튜버마다 **수익 구조, 인기도, 팬덤, 플랫폼 의존도, 대응역량**이 다르기 때문에, **고정된 DRI 피처 가중치만**으로는 동일한 온라인 확산 패턴이라도 **보험·손해사정 관점 위험이 같다고 보기 어렵습니다.** 그래서 이 MVP는 **`Creator Profile` / `Monetization Profile`** 레이어를 두고,

- 같은 지표 신호라도 **크리에이터별 피처 가중치**(롱폼·광고·팬덤 등 민감도)를 조정하고,
- 결합 결과 **Raw DRI**(확산 강도)에 **취약성 배수**를 곱한 **Adjusted DRI**으로 트리거를 두며,
- **손해 영향 가능 수익원**·증빙 우선 순위(proxy), **premium proxy**(상품 참고값, 확정료 아님)를 제안합니다.

샘플 CSV: **`data/sample_creator_profiles.csv`** — 앱에서는 **Creator T / Creator A** 선택 또는 슬라이더 **직접 입력**이 가능합니다. 사이드바에서 **크리에이터 프로필 보정**을 끄면 기존과 같이 고정 가중치·배수 1.0만 사용합니다.

## 실행 방법

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## `.env` 설정 (선택)

1. `.env.example`을 복사해 `.env`로 저장합니다.
2. **`OPENAI_API_KEY`**: 사이드바에서 **Mock LLM/룰 강제**를 끄면, 우선순위 상위 **N개(기본 10)** 후보만 `OpenAILLMClient`로 분류합니다.
3. **리포트 ‘AI 판단 요약’** 토글이 켜져 있으면, 동일 키로 **요약 소절만** 추가 호출할 수 있습니다(Mock 분류와 독립).
4. **YouTube / Naver DataLab**: `YOUTUBE_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 있으면 `live_api`·`hybrid`에서 실제 호출을 시도하고, 없거나 실패 시 **선택한 CSV로 폴백**합니다.
5. **DRI z→0~100 완화**: `DRI_Z_SCORE_DIVISOR`(기본 8)로 조정합니다.

## 데이터 소스 모드 (`data_source_mode`)

| 모드 | 동작 |
|------|------|
| `csv_mock` | 일별·후보 영상은 **사이드바에서 고른 샘플 CSV만** 사용합니다. |
| `live_api` | 키가 있으면 YouTube·Naver를 우선 시도하고, 부족분은 CSV로 보강합니다. |
| `hybrid` | CSV와 API 결과를 **날짜 기준으로 병합**합니다. |

BigKinds·SocialBlade·Vling **자동 크롤링은 연동하지 않습니다.** 공개 채널 지표는 **수동 CSV**(`public_channel_analytics_collector`, `data/sample_channel_analytics_manual.csv` 참고) 또는 향후 provider 확장을 전제로 합니다.

## 케이스 모드

| 모드 | 설명 |
|------|------|
| `mock_demo` | 데모용. 기본적으로 **분석 시작일 이전 최대 30일**을 자동 baseline 윈도로 삼습니다(수동 가능). |
| `historical_case` | 사후 재현. 사용자가 **baseline_start ~ baseline_end**, **analysis_start ~ analysis_end**를 지정합니다. |

## 샘플 데이터

- `data/sample_*` : 가명 **Creator A** 중심 표준 샘플  
- `data/sample_case_creator_t_*` : 가명 **Creator T** 사례형 스파이크(실명 사용 없음)  
- `data/sample_video_snapshots.csv` : **향후** 1~5분 단위 스냅샷으로 velocity 확장할 때용 예시 레이아웃

발표용 지표 분포를 바꾸려면 `scripts/generate_sample_metrics.py`를 참고해 일별 CSV를 재생성할 수 있습니다 (베이스라인 분리 전제).

## DRI 수식 (업데이트)

정량 피처는 **사용자 지정 baseline CSV 구간**으로 잡은 평균·표준편차 대비 z-score → 0~100.  
NLP/룰 보조 피처는 0~1 → ×100. 결측 시 해당 가중치를 제외하고 **재정규화**합니다.

\[
\begin{aligned}
\text{DRI}_t =\;&
0.20 \cdot \text{Risk Candidate Content Spike}
+ 0.15 \cdot \text{Candidate Content Exposure Spike}\\
&+ 0.15 \cdot \text{Comment Spike(일별 합)}
+ 0.10 \cdot \text{Search Spike}
+ 0.10 \cdot \text{News Amplification}\\
&+ 0.10 \cdot \text{Toxicity}
+ 0.10 \cdot \text{Narrative Duplication}
+ 0.10 \cdot \text{Creator Targeting Context}
\end{aligned}
\]

> `Candidate Content Exposure Spike`는 현재 **일별 후보 영상 총 조회수** 규모 신호입니다. **진짜 velocity**는 운영 시 `sample_video_snapshots` 형태의 시계열 적재 후 추가할 수 있습니다.

## 운영 시나리오와 한계

- **실시간 운영(가정)**: 1~5분 간격 snapshot을 저장해 노출·댓글 **velocity**까지 반영한 DRI 업데이트.  
- **현재 MVP**: 키 없이 **CSV + mock·제한 LLM**으로도 동작하고, 키가 있으면 **실제 API 분기**로 데모할 수 있습니다. `historical_case`는 **사후 백테스트/재현**에 가깝습니다.
- 딥페이크 API 상시 검출, 전체 댓글 LLM 일괄 분석, DB/로그인/결제 등은 **비범위**입니다.

## AI·NLP가 들어가는 위치

1. **표적화·문맥**(OpenAI 또는 mock, **상위 우선순위 N건만** API 호출) — `src/ai_classifier.py`, `src/llm_client.py`  
2. **Toxicity mock** — `src/models/toxicity_model.py` (HF TODO)  
3. **내러티브 중복** — `src/models/embedding_cluster_model.py` (sentence-transformers 교체 TODO)  
4. **손해사정 리포트 초안** — `src/report_generator.py`

## 프로젝트 구조

```
(저장소 루트)
  app.py
  README.md
  requirements.txt
  .env.example
  data/
  reports/
  src/
    models/
    collectors/
    ...
```

## 외부 데이터/API 연동 예정 위치

| 구분 | 파일 |
|------|------|
| YouTube 검색·댓글 | `src/collectors/youtube_collector.py` |
| 검색 트렌드 | `src/collectors/naver_datalab_collector.py` |
| 뉴스 건수 | `src/collectors/bigkinds_collector.py` |
| 공개 채널 메트릭(수동 CSV·provider 확장) | `src/collectors/public_channel_analytics_collector.py` |
