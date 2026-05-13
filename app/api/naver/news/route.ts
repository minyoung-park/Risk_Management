import { NextRequest, NextResponse } from 'next/server';

const CLIENT_ID     = process.env.NAVER_CLIENT_ID     ?? '';
const CLIENT_SECRET = process.env.NAVER_CLIENT_SECRET ?? '';

const strip = (s: string) => s.replace(/<[^>]+>/g, '');

export async function GET(req: NextRequest) {
  if (!CLIENT_ID || !CLIENT_SECRET)
    return NextResponse.json({ error: 'Naver API keys not configured' }, { status: 500 });

  const query = req.nextUrl.searchParams.get('query') ?? '';
  const res = await fetch(
    `https://openapi.naver.com/v1/search/news.json?query=${encodeURIComponent(query)}&display=100&sort=date`,
    { headers: { 'X-Naver-Client-Id': CLIENT_ID, 'X-Naver-Client-Secret': CLIENT_SECRET } },
  );

  const data = await res.json();
  const items = (data.items ?? []).map((item: Record<string, string>) => ({
    title:       strip(item.title),
    link:        item.link,
    description: strip(item.description),
    pubDate:     item.pubDate,
  }));

  return NextResponse.json(items);
}
