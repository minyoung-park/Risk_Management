// LLM API 서비스 (Claude / GPT)
// USE_MOCK=false + NEXT_PUBLIC_LLM_API_KEY 설정 시 실제 API 호출
// 민감 정보는 절대 LLM에 입력하지 않음 (types.ts 의 민감 데이터 목록 참고)

const USE_MOCK = true;

export interface LLMSummaryInput {
  creatorName: string;
  driScore: number;
  driStage: string;
  topSignals: string[];
  relatedVideos: number;
  toxicityRate: number;
  hasMCN: boolean;
  hasLawyer: boolean;
}

export interface LLMSummaryResult {
  summary: string;           // 가입자용 쉬운 요약
  adjusterMemo: string;      // 손해사정사용 심사 메모
  prDraft: string;           // PR 문안 초안
  recommendedActions: string[];
}

// ─── Mock 데이터 ──────────────────────────────────────────────────────────────

const MOCK_SUMMARY: LLMSummaryResult = {
  summary:
    '현재 귀하의 채널은 Trigger 단계(DRI 78점)에 진입했습니다. ' +
    '제3자 관련 영상 43개가 확산 중이며 총 1억 3천만 뷰 이상 노출되었습니다. ' +
    '댓글 독성 비율이 24%로 높은 수준입니다. 즉각적인 증거보존과 MCN 담당자 연락을 권장합니다.',
  adjusterMemo:
    'DRI 78점, Trigger 단계 진입. 유해 콘텐츠 노출 점수(88)가 가장 높으며 ' +
    '제3자 영상 43개·총 조회수 1.34억이 주요 근거. ' +
    'YouTube Analytics 미연동으로 수익중단손해 산정 불가. 담보 적용 가능성: 평판공격·법률대응 높음.',
  prDraft:
    '안녕하세요, [채널명]입니다.\n' +
    '최근 확산된 일부 게시물에 대해 팬 여러분께 상황을 공유드립니다.\n' +
    '현재 사실 확인 및 법률 검토를 진행 중이며, 확인된 내용을 바탕으로 공식 입장을 드리겠습니다.\n' +
    '불필요한 추측과 2차 가공을 자제해 주시길 부탁드립니다.',
  recommendedActions: [
    '댓글에 직접 대응하지 마세요.',
    '문제 URL을 먼저 증거보존하세요.',
    'MCN 담당자에게 사건 요약을 공유하세요.',
    '플랫폼 신고를 준비하세요.',
    '공식 입장문 배포 전 법률 검토를 받으세요.',
  ],
};

// ─── 공개 API ────────────────────────────────────────────────────────────────

export async function generateSummary(input: LLMSummaryInput): Promise<LLMSummaryResult> {
  if (USE_MOCK) return MOCK_SUMMARY;

  // 실제 호출: /api/llm/summary 프록시 사용 (API 키 서버사이드 보호)
  const res = await fetch('/api/llm/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  return res.json();
}
