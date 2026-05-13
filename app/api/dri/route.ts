import { NextRequest, NextResponse } from 'next/server';
import { calculateDRI, rawToSignals } from '../../../src/services/dri';
import type { RawSignalData } from '../../../src/services/dri';

const YT_KEY       = process.env.YOUTUBE_API_KEY     ?? '';
const NAVER_ID     = process.env.NAVER_CLIENT_ID     ?? '';
const NAVER_SECRET = process.env.NAVER_CLIENT_SECRET ?? '';
const LLM_KEY      = process.env.LLM_API_KEY         ?? '';
const YT_BASE      = 'https://www.googleapis.com/youtube/v3';
const NAVER_BASE   = 'https://openapi.naver.com/v1';

// ── 해시 기반 중복률 ─────────────────────────────────────────────────────────
function duplicateRate(comments: string[]): number {
  if (!comments.length) return 0;
  const seen = new Set<string>();
  let dupes = 0;
  for (const c of comments) {
    const key = c.trim().replace(/\s+/g, ' ').toLowerCase();
    if (seen.has(key)) dupes++;
    else seen.add(key);
  }
  return dupes / comments.length;
}

// ── Claude 독성 분석 ──────────────────────────────────────────────────────────
async function analyzeToxicity(comments: string[]) {
  if (!LLM_KEY || !comments.length)
    return { toxicityRate: 0, negativeStanceRate: 0 };

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

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method:  'POST',
      headers: {
        'Content-Type':      'application/json',
        'x-api-key':         LLM_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model:      'claude-sonnet-4-6',
        max_tokens: 64,
        messages:   [{ role: 'user', content: prompt }],
      }),
    });
    const data  = await res.json();
    const text  = data.content?.[0]?.text ?? '{}';
    const match = text.match(/\{[\s\S]*\}/);
    const parsed = JSON.parse(match?.[0] ?? '{}');
    return {
      toxicityRate:       Math.min(1, Math.max(0, parsed.toxicityRate       ?? 0)),
      negativeStanceRate: Math.min(1, Math.max(0, parsed.negativeStanceRate ?? 0)),
    };
  } catch {
    return { toxicityRate: 0, negativeStanceRate: 0 };
  }
}

export async function GET(req: NextRequest) {
  const keyword = req.nextUrl.searchParams.get('keyword') ?? '';
  if (!keyword)
    return NextResponse.json({ error: 'keyword required' }, { status: 400 });
  if (!YT_KEY || !NAVER_ID)
    return NextResponse.json({ error: 'API keys not configured' }, { status: 500 });

  // ── 1. 크리에이터 채널 ID 파악 (제3자 필터링용) ────────────────────────────
  const channelSearchRes  = await fetch(
    `${YT_BASE}/search?part=snippet&q=${encodeURIComponent(keyword)}&type=channel&maxResults=1&key=${YT_KEY}`,
  );
  const channelSearchData = await channelSearchRes.json();
  const creatorChannelId: string =
    channelSearchData.items?.[0]?.snippet?.channelId ?? '';

  // ── 2. YouTube: 관련 영상 검색 후 제3자만 필터링 ──────────────────────────
  const searchRes  = await fetch(
    `${YT_BASE}/search?part=snippet&q=${encodeURIComponent(keyword)}&type=video&maxResults=50&order=viewCount&key=${YT_KEY}`,
  );
  const searchData = await searchRes.json();

  const allItems        = searchData.items ?? [];
  const thirdPartyItems = creatorChannelId
    ? allItems.filter(
        (i: { snippet: { channelId: string } }) =>
          i.snippet.channelId !== creatorChannelId,
      )
    : allItems;
  const videoIds: string[] = thirdPartyItems.map(
    (i: { id: { videoId: string } }) => i.id.videoId,
  );

  // ── 3. YouTube: 제3자 영상 통계 + 댓글 수집 (상위 5개) ────────────────────
  let totalViews         = 0;
  let recentCommentCount = 0;
  const commentTexts: string[] = [];

  if (videoIds.length > 0) {
    const statsRes  = await fetch(
      `${YT_BASE}/videos?part=statistics&id=${videoIds.slice(0, 50).join(',')}&key=${YT_KEY}`,
    );
    const statsData = await statsRes.json();
    for (const item of statsData.items ?? [])
      totalViews += parseInt(item.statistics.viewCount ?? '0');

    const oneDayAgo = new Date(Date.now() - 864e5).toISOString();
    for (const vid of videoIds.slice(0, 5)) {
      try {
        const cmtRes  = await fetch(
          `${YT_BASE}/commentThreads?part=snippet&videoId=${vid}&maxResults=100&order=time&key=${YT_KEY}`,
        );
        const cmtData = await cmtRes.json();
        for (const item of cmtData.items ?? []) {
          const s    = item.snippet.topLevelComment.snippet;
          commentTexts.push(s.textDisplay as string);
          if (s.publishedAt >= oneDayAgo) recentCommentCount++;
        }
      } catch { /* 댓글 비활성 영상 무시 */ }
    }
  }

  // ── 4. Naver DataLab: 최근 30일 → 최근 7일 vs 이전 23일 급등 비율 ─────────
  const today     = new Date().toISOString().slice(0, 10);
  const thirtyAgo = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);

  const trendRes = await fetch(`${NAVER_BASE}/datalab/search`, {
    method:  'POST',
    headers: {
      'Content-Type':          'application/json',
      'X-Naver-Client-Id':     NAVER_ID,
      'X-Naver-Client-Secret': NAVER_SECRET,
    },
    body: JSON.stringify({
      startDate:     thirtyAgo,
      endDate:       today,
      timeUnit:      'date',
      keywordGroups: [{ groupName: keyword, keywords: [keyword] }],
    }),
  });
  const trendData   = await trendRes.json();
  const trendPoints = trendData.results?.[0]?.data ?? [];

  // 최근 7일 평균 vs 이전 평균 비율로 급등 감지
  const recent7 = trendPoints.slice(-7) as { ratio: number }[];
  const prev    = trendPoints.slice(0, -7) as { ratio: number }[];
  const avg     = (pts: { ratio: number }[]) =>
    pts.length ? pts.reduce((s, p) => s + p.ratio, 0) / pts.length : 0;
  const recent7avg = avg(recent7);
  const prevAvg    = avg(prev);
  // 2배 급등 = 100점, 평소와 같음 = 0점
  const spikeRatio      = prevAvg > 0
    ? Math.max(0, recent7avg / prevAvg - 1)
    : (recent7avg > 0 ? 1 : 0);
  const searchSpikeScore = Math.min(spikeRatio * 50, 100);

  // ── 5. Naver: 최근 30일 뉴스·블로그 + 독성 분석 (병렬) ───────────────────
  const [newsRes, blogRes, toxicity] = await Promise.all([
    fetch(
      `${NAVER_BASE}/search/news.json?query=${encodeURIComponent(keyword)}&display=100&sort=date`,
      { headers: { 'X-Naver-Client-Id': NAVER_ID, 'X-Naver-Client-Secret': NAVER_SECRET } },
    ),
    fetch(
      `${NAVER_BASE}/search/blog.json?query=${encodeURIComponent(keyword)}&display=100&sort=date`,
      { headers: { 'X-Naver-Client-Id': NAVER_ID, 'X-Naver-Client-Secret': NAVER_SECRET } },
    ),
    analyzeToxicity(commentTexts),
  ]);

  const newsData = await newsRes.json();
  const blogData = await blogRes.json();

  const sevenDaysAgo = Date.now() - 7 * 864e5;

  // 최근 7일 이내 뉴스만 카운트 (pubDate: RFC 822)
  const recentNewsCount = (newsData.items ?? []).filter(
    (item: { pubDate: string }) => {
      try { return new Date(item.pubDate).getTime() >= sevenDaysAgo; }
      catch { return false; }
    },
  ).length;

  // 최근 7일 이내 블로그만 카운트 (postdate: 'YYYYMMDD')
  const recentBlogCount = (blogData.items ?? []).filter(
    (item: { postdate: string }) => {
      try {
        const d = item.postdate ?? '';
        const parsed = new Date(`${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`);
        return parsed.getTime() >= sevenDaysAgo;
      } catch { return false; }
    },
  ).length;

  // ── 6. Raw signals 조립 ───────────────────────────────────────────────────
  const avgDaily         = 10;
  const commentVelocityZ = Math.max(
    (recentCommentCount - avgDaily) / Math.max(avgDaily * 0.5, 1),
    0,
  );

  const raw: RawSignalData = {
    searchTrendPeak:        searchSpikeScore,  // 0-100 spike score (2배 급등 = 100)
    commentVelocityZ,
    toxicityRate:           toxicity.toxicityRate,
    negativeStanceRate:     toxicity.negativeStanceRate,
    duplicateRate:          duplicateRate(commentTexts),
    relatedVideoCount:      videoIds.length,   // 제3자 영상 수
    totalExposureViews:     totalViews,        // 제3자 영상 총 조회수
    newsCount:              recentNewsCount,   // 최근 30일 뉴스 수 (0-100)
    snsCount:               0,
    blogCount:              recentBlogCount,   // 최근 30일 블로그 수 (0-100)
    suspiciousPatternScore: 0,
    viewDropRate:           0,
    uploadGapDays:          0,
  };

  // ── 7. DRI 계산 ───────────────────────────────────────────────────────────
  const signals = rawToSignals(raw);
  const result  = calculateDRI(signals);

  return NextResponse.json({
    ...result,
    meta: {
      thirdPartyVideoCount: videoIds.length,
      totalExposureViews:   totalViews,
      recentNewsCount,
      recentBlogCount,
      searchSpikeScore:     Math.round(searchSpikeScore),
      recent7dayAvg:        Math.round(recent7avg),
      prevPeriodAvg:        Math.round(prevAvg),
      toxicityRate:         toxicity.toxicityRate,
      commentCount:         commentTexts.length,
      creatorChannelId,
    },
  });
}
