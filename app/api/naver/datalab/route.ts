import { NextRequest, NextResponse } from 'next/server';

const CLIENT_ID     = process.env.NAVER_CLIENT_ID     ?? '';
const CLIENT_SECRET = process.env.NAVER_CLIENT_SECRET ?? '';

export async function POST(req: NextRequest) {
  if (!CLIENT_ID || !CLIENT_SECRET)
    return NextResponse.json({ error: 'Naver API keys not configured' }, { status: 500 });

  const { keyword } = await req.json();
  const today        = new Date().toISOString().slice(0, 10);
  const thirtyAgo    = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);

  const res = await fetch('https://openapi.naver.com/v1/datalab/search', {
    method: 'POST',
    headers: {
      'Content-Type':          'application/json',
      'X-Naver-Client-Id':     CLIENT_ID,
      'X-Naver-Client-Secret': CLIENT_SECRET,
    },
    body: JSON.stringify({
      startDate:     thirtyAgo,
      endDate:       today,
      timeUnit:      'date',
      keywordGroups: [{ groupName: keyword, keywords: [keyword] }],
    }),
  });

  const data = await res.json();
  const points = (data.results?.[0]?.data ?? []).map((d: { period: string; ratio: number }) => ({
    period: d.period,
    ratio:  d.ratio,
  }));

  return NextResponse.json(points);
}
