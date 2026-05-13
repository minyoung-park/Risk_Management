import { NextRequest, NextResponse } from 'next/server';

const CLIENT_ID     = process.env.NAVER_CLIENT_ID     ?? '';
const CLIENT_SECRET = process.env.NAVER_CLIENT_SECRET ?? '';

export async function GET(req: NextRequest) {
  if (!CLIENT_ID || !CLIENT_SECRET)
    return NextResponse.json({ error: 'Naver API keys not configured' }, { status: 500 });

  const query = req.nextUrl.searchParams.get('query') ?? '';
  const res = await fetch(
    `https://openapi.naver.com/v1/search/blog.json?query=${encodeURIComponent(query)}&display=1`,
    { headers: { 'X-Naver-Client-Id': CLIENT_ID, 'X-Naver-Client-Secret': CLIENT_SECRET } },
  );

  const data = await res.json();
  return NextResponse.json({ total: data.total ?? 0 });
}
