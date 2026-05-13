import { NextRequest, NextResponse } from 'next/server';
import type { LLMSummaryInput, LLMSummaryResult } from '../../../../src/services/llm';

const OPENAI_KEY    = process.env.OPENAI_API_KEY ?? '';
const ANTHROPIC_KEY = process.env.LLM_API_KEY    ?? '';

// OpenAI 키가 있으면 gpt-4o-mini, 없으면 Claude Haiku
const PROVIDER = OPENAI_KEY ? 'openai' : 'anthropic';

function buildPrompt(input: LLMSummaryInput): string {
  const toxPct = (input.toxicityRate * 100).toFixed(1);
  const mcn    = input.hasMCN    ? '있음' : '없음';
  const lawyer = input.hasLawyer ? '있음' : '없음';

  return `당신은 크리에이터 평판 위기 보험 전문 AI입니다.
아래 모니터링 지표를 바탕으로 세 가지 문서를 작성하세요.

[입력 데이터]
- 크리에이터: ${input.creatorName}
- DRI 점수: ${input.driScore}점 / 단계: ${input.driStage}
- 주요 위험 신호: ${input.topSignals.join(', ')}
- 관련 영상 수: ${input.relatedVideos}개
- 독성 댓글 비율: ${toxPct}%
- MCN 소속: ${mcn}
- 법률 담당자: ${lawyer}

[작성 지침]
1. summary (가입자용): 지금 상황이 왜 심각한지, 무엇을 해야 하는지를 2~3문장으로. 숫자를 활용해 구체적으로.
2. adjusterMemo (손해사정사용): DRI 점수 근거, 담보 적용 가능성, 산정 필요 항목을 3~5줄로. 전문 용어 사용 가능.
3. prDraft (공식 입장문 초안): 팬·대중을 향한 150자 내외의 진정성 있는 문장. [채널명] 플레이스홀더 사용.
4. recommendedActions: 지금 당장 해야 할 행동 5가지. 우선순위 순으로.

JSON만 반환 (설명·마크다운 없이):
{
  "summary": "...",
  "adjusterMemo": "...",
  "prDraft": "...",
  "recommendedActions": ["...", "...", "...", "...", "..."]
}`;
}

async function callOpenAI(prompt: string): Promise<string> {
  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${OPENAI_KEY}`,
    },
    body: JSON.stringify({
      model:       'gpt-4o-mini',
      max_tokens:  1024,
      temperature: 0.3,
      messages:    [{ role: 'user', content: prompt }],
    }),
  });
  const data = await res.json();
  return data.choices?.[0]?.message?.content ?? '{}';
}

async function callAnthropic(prompt: string): Promise<string> {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method:  'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         ANTHROPIC_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model:      'claude-haiku-4-5-20251001',
      max_tokens: 1024,
      messages:   [{ role: 'user', content: prompt }],
    }),
  });
  const data = await res.json();
  return data.content?.[0]?.text ?? '{}';
}

export async function POST(req: NextRequest) {
  if (!OPENAI_KEY && !ANTHROPIC_KEY)
    return NextResponse.json({ error: 'LLM API key not configured' }, { status: 500 });

  const input: LLMSummaryInput = await req.json();
  const prompt = buildPrompt(input);

  try {
    const text = PROVIDER === 'openai'
      ? await callOpenAI(prompt)
      : await callAnthropic(prompt);

    const match = text.match(/\{[\s\S]*\}/);
    const result: LLMSummaryResult = JSON.parse(match?.[0] ?? text);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ error: 'LLM 응답 파싱 실패' }, { status: 500 });
  }
}
