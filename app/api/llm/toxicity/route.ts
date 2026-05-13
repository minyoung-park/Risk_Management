import { NextRequest, NextResponse } from 'next/server';

const API_KEY = process.env.LLM_API_KEY ?? '';

export interface ToxicityAnalysis {
  toxicityRate: number;       // 0~1  욕설·혐오·공격적 표현 비율
  negativeStanceRate: number; // 0~1  크리에이터에 대한 부정적 감정 비율
  duplicateRate: number;      // 0~1  해시 기반 중복 댓글 비율
}

function calcDuplicateRate(comments: string[]): number {
  if (comments.length === 0) return 0;
  const seen = new Set<string>();
  let dupes = 0;
  for (const c of comments) {
    const key = c.trim().replace(/\s+/g, ' ').toLowerCase();
    if (seen.has(key)) dupes++;
    else seen.add(key);
  }
  return dupes / comments.length;
}

export async function POST(req: NextRequest) {
  const { comments }: { comments: string[] } = await req.json();
  if (!comments?.length)
    return NextResponse.json({ toxicityRate: 0, negativeStanceRate: 0, duplicateRate: 0 });

  const duplicateRate = calcDuplicateRate(comments);

  if (!API_KEY)
    return NextResponse.json({ toxicityRate: 0, negativeStanceRate: 0, duplicateRate }, { status: 500 });

  // 최대 300개 샘플링 (비용·속도 균형)
  const sample   = comments.slice(0, 300);
  const numbered = sample.map((c, i) => `${i + 1}. ${c}`).join('\n');

  const prompt = `당신은 한국어 유튜브 댓글 분석 전문가입니다.
아래 댓글들을 분석해 두 가지 비율을 정확하게 추정하세요.

[댓글 목록]
${numbered}

[판단 기준]
- toxicityRate: 욕설, 혐오 표현, 직접적 공격, 비하가 포함된 댓글 비율
- negativeStanceRate: 크리에이터에 대한 실망·비난·불신·배신감 등 부정적 감정을 담은 댓글 비율
  (단순 사실 언급이나 중립 반응은 제외)

JSON만 반환 (설명 없이):
{"toxicityRate": 0.00, "negativeStanceRate": 0.00}`;

  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method:  'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model:      'claude-sonnet-4-6',
      max_tokens: 64,
      messages:   [{ role: 'user', content: prompt }],
    }),
  });

  const data = await res.json();
  const text = data.content?.[0]?.text ?? '{}';

  try {
    const match  = text.match(/\{[\s\S]*\}/);
    const parsed = JSON.parse(match?.[0] ?? '{}');
    return NextResponse.json({
      toxicityRate:       Math.min(1, Math.max(0, parsed.toxicityRate       ?? 0)),
      negativeStanceRate: Math.min(1, Math.max(0, parsed.negativeStanceRate ?? 0)),
      duplicateRate,
    } satisfies ToxicityAnalysis);
  } catch {
    return NextResponse.json({ toxicityRate: 0, negativeStanceRate: 0, duplicateRate });
  }
}
