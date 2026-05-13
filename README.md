# Risk_Management — AI 안심 케어 보험 모니터링 대시보드

유튜버·스트리머 대상 온라인 평판 위기 보험의 AI 모니터링 대시보드 프로토타입입니다.

## 실행 방법

```bash
npm install
npm run dev
```

`http://localhost:3000` 에서 확인

## 구조

- `src/services/` — YouTube / Naver / LLM API 서비스 레이어 (USE_MOCK=true)
- `src/models/driCalculator.ts` — DRI 점수 계산 모델
- `src/components/` — 가입자 View / 손해사정사 View 컴포넌트
- `src/data/mockData.ts` — 목업 데이터
