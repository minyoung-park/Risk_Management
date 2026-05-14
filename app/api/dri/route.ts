import { NextRequest, NextResponse } from 'next/server';
import { calculateDRI, rawToSignals } from '../../../src/services/dri';
import type { RawSignalData } from '../../../src/services/dri';

const YT_KEY       = process.env.YOUTUBE_API_KEY     ?? '';
const NAVER_ID     = process.env.NAVER_CLIENT_ID     ?? '';
const NAVER_SECRET = process.env.NAVER_CLIENT_SECRET ?? '';
const LLM_KEY      = process.env.LLM_API_KEY         ?? '';
const YT_BASE      = 'https://www.googleapis.com/youtube/v3';
const NAVER_BASE   = 'https://openapi.naver.com/v1';

// ── 유틸 ──────────────────────────────────────────────────────────────────────
const mean = (arr: number[]) =>
  arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

const std = (arr: number[]) => {
  const m = mean(arr);
  return Math.sqrt(mean(arr.map(v => Math.pow(v - m, 2))));
};

// ── Google Trends 비공식 API (실패 시 빈 배열 반환) ───────────────────────────
async function fetchGoogleTrends(keyword: string, startDate: string, endDate: string): Promise<number[]> {
  try {
    const timeRange  = `${startDate} ${endDate}`;
    const exploreReq = JSON.stringify({
      comparisonItem: [{ keyword, geo: 'KR', time: timeRange }],
      category: 0, property: '',
    });
    const exploreRes = await fetch(
      `https://trends.google.com/trends/api/explore?hl=ko&tz=-540&req=${encodeURIComponent(exploreReq)}`,
      { headers: { 'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ko-KR,ko;q=0.9' } },
    );
    const exploreData = JSON.parse((await exploreRes.text()).replace(/^\)\]\}'\n/, ''));
    const token = (exploreData.widgets ?? []).find((w: { id: string }) => w.id === 'TIMESERIES')?.token;
    if (!token) return [];

    const multilineReq = JSON.stringify({
      time: timeRange, resolution: 'WEEK', locale: 'ko',
      comparisonItem: [{ geo: 'KR', complexKeywordsRestriction: { keyword: [{ type: 'BROAD', value: keyword }] } }],
      requestOptions: { property: '', backend: 'CM', category: 0 },
    });
    const multilineRes = await fetch(
      `https://trends.google.com/trends/api/multiline?hl=ko&tz=-540&req=${encodeURIComponent(multilineReq)}&token=${encodeURIComponent(token)}`,
      { headers: { 'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ko-KR,ko;q=0.9' } },
    );
    const multilineData = JSON.parse((await multilineRes.text()).replace(/^\)\]\}'\n/, ''));
    return (multilineData.default?.timelineData ?? []).map(
      (d: { value: number[] }) => d.value?.[0] ?? 0,
    );
  } catch { return []; }
}

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

// ISO 8601 duration → 초 (Shorts 판별용)
function durationToSec(iso: string): number {
  const m = iso.match(/^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/);
  if (!m) return 9999;
  return (parseInt(m[1] ?? '0') * 3600)
       + (parseInt(m[2] ?? '0') * 60)
       +  parseInt(m[3] ?? '0');
}

// ── 영상 기반 독성 분석 (노트북 방식) ────────────────────────────────────────
// 노트북 독성 키워드 (오킹_DRI.ipynb Cell 28 기준)
const TOXIC_KEYWORDS = [
  '코인','스캠','사기','사기꾼','거짓말','환불','피해자','고소',
  '신고','구독취소','나락','퇴출','실망','해명','사과','빼박','주작','실체','증거','불매',
  '협박','공갈','갈취','논란','렉카','고발','파렴치',
];

async function fetchTranscript(videoId: string): Promise<string> {
  try {
    const res = await fetch(
      `https://www.youtube.com/api/timedtext?lang=ko&v=${videoId}&fmt=srv3`,
    );
    if (!res.ok) return '';
    const xml = await res.text();
    const texts = [...xml.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/g)].map(m => m[1]);
    return texts.join(' ')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&#39;/g, "'").replace(/&quot;/g, '"');
  } catch { return ''; }
}

async function analyzeVideoToxicity(
  videos: Array<{ videoId: string; title: string }>,
): Promise<number> {
  if (!videos.length) return 0;

  // ① 제목 독성 키워드 비율
  const titleToxicCount = videos.filter(v =>
    TOXIC_KEYWORDS.some(kw => v.title.includes(kw)),
  ).length;
  const titleToxicRatio = titleToxicCount / videos.length;

  // ② 자막 독성 키워드 비율 (상위 10개만)
  const sample = videos.slice(0, 10);
  const transcripts = await Promise.all(sample.map(v => fetchTranscript(v.videoId)));
  const scriptToxicCount = transcripts.filter(t =>
    t.length > 10 && TOXIC_KEYWORDS.some(kw => t.includes(kw)),
  ).length;
  const scriptToxicRatio = sample.length > 0 ? scriptToxicCount / sample.length : 0;

  // ③ 부정 감성 비율 — 영상 제목으로 Claude 판단
  let negRatio = 0;
  if (LLM_KEY && videos.length > 0) {
    const titleList = videos.slice(0, 20).map((v, i) => `${i + 1}. ${v.title}`).join('\n');
    try {
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': LLM_KEY, 'anthropic-version': '2023-06-01' },
        body: JSON.stringify({
          model: 'claude-haiku-4-5-20251001', max_tokens: 64,
          messages: [{ role: 'user', content: `다음 유튜브 영상 제목들 중 크리에이터에 대한 비판/비난/부정적 내용의 비율을 0~1로 추정하세요. JSON만 반환:\n${titleList}\n\n{"negativeRatio": 0.00}` }],
        }),
      });
      const data   = await res.json();
      const parsed = JSON.parse((data.content?.[0]?.text ?? '{}').match(/\{[\s\S]*\}/)?.[0] ?? '{}');
      negRatio = Math.min(1, Math.max(0, parsed.negativeRatio ?? 0));
    } catch {}
  }

  // 노트북 공식: neg×0.50 + title_toxic×0.30 + script_toxic×0.20
  return Math.min(100, negRatio * 50 + titleToxicRatio * 30 + scriptToxicRatio * 20);
}

// ── 댓글 수집 ─────────────────────────────────────────────────────────────────
async function fetchComments(videoIds: string[], maxPerVideo = 100) {
  const texts: string[]          = [];
  const authorCounts             = new Map<string, number>();
  const publishedAts: string[]   = [];

  for (const vid of videoIds) {
    try {
      const res  = await fetch(
        `${YT_BASE}/commentThreads?part=snippet&videoId=${vid}&maxResults=${maxPerVideo}&order=time&key=${YT_KEY}`,
      );
      const data = await res.json();
      for (const item of data.items ?? []) {
        const s        = item.snippet.topLevelComment.snippet;
        const authorId = s.authorChannelId?.value ?? '';
        texts.push(s.textDisplay as string);
        publishedAts.push(s.publishedAt as string);
        if (authorId) authorCounts.set(authorId, (authorCounts.get(authorId) ?? 0) + 1);
      }
    } catch { /* 댓글 비활성 영상 무시 */ }
  }
  return { texts, authorCounts, publishedAts };
}

// ── Manipulation Signal (노트북 4-factor) ─────────────────────────────────────
function calcManipulationScore(
  texts: string[],
  authorCounts: Map<string, number>,
  publishedAts: string[],
): number {
  const total = texts.length;
  if (!total) return 0;

  // ① 동일 문구 반복 비율 (복붙 어택)
  const cleaned  = texts.map(t => t.toLowerCase().trim().replace(/\s+/g, ' '));
  const textFreq = new Map<string, number>();
  for (const t of cleaned) textFreq.set(t, (textFreq.get(t) ?? 0) + 1);
  const dupCount = [...textFreq.values()].filter(n => n > 1).reduce((s, n) => s + n, 0);
  const dupRatio = dupCount / total * 100;

  // ② 극단적으로 짧은 댓글 비율 (<5자, 봇 패턴)
  const shortRatio = texts.filter(t => t.trim().length < 5).length / total * 100;

  // ③ 동일 계정 3회 이상 반복 비율
  const totalAccounts   = authorCounts.size;
  const repeatAccounts  = [...authorCounts.values()].filter(n => n >= 3).length;
  const repeatRatio     = totalAccounts > 0 ? repeatAccounts / totalAccounts * 100 : 0;

  // ④ 독성 단문 댓글 비율 (악성 봇 패턴 - 논란 키워드 포함 단문)
  const toxicKw = ['협박', '공갈', '갈취', '사기', '논란', '렉카', '고발', '사기꾼', '거짓말', '파렴치'];
  const toxicShortRatio = texts.filter(t =>
    t.trim().length < 20 && toxicKw.some(kw => t.includes(kw)),
  ).length / total * 100;

  // ⑤ 특정 시간대 집중 비율 (30% 이상 집중 시 추가)
  const hourCounts = new Map<number, number>();
  for (const pa of publishedAts) {
    const h = new Date(pa).getHours();
    hourCounts.set(h, (hourCounts.get(h) ?? 0) + 1);
  }
  const maxHourRatio = Math.max(...hourCounts.values(), 0) / total * 100;
  const timeConcentration = maxHourRatio > 30 ? maxHourRatio - 30 : 0;

  return Math.min(100,
    dupRatio          * 0.30 +
    shortRatio        * 0.18 +
    repeatRatio       * 0.22 +
    toxicShortRatio   * 0.20 +
    timeConcentration * 0.10,
  );
}

export async function GET(req: NextRequest) {
  const keyword  = req.nextUrl.searchParams.get('keyword') ?? '';
  const nameParam = req.nextUrl.searchParams.get('name') ?? ''; // 한글 이름 직접 입력 시 Naver 검색에 사용
  if (!keyword)
    return NextResponse.json({ error: 'keyword required' }, { status: 400 });
  if (!YT_KEY || !NAVER_ID)
    return NextResponse.json({ error: 'API keys not configured' }, { status: 500 });

  // 기준일: 쿼리 파라미터 date (YYYY-MM-DD), 없으면 오늘
  const refDate = req.nextUrl.searchParams.get('date') ?? new Date().toISOString().slice(0, 10);
  const refTs   = new Date(refDate).getTime();

  // ════════════════════════════════════════════════════════════════════════════
  // STEP 1 — 채널 ID 확보
  //   · UC... 직접 입력 → 그대로 사용 (API 호출 없음)
  //   · @handle → channels?forHandle= (정확)
  //   · 키워드 → search?type=channel (fallback)
  // ════════════════════════════════════════════════════════════════════════════
  let creatorChannelId = '';
  let searchKeyword = keyword; // Naver·YouTube 검색에 쓸 실제 채널명

  // 채널 타이틀에서 Naver 검색용 한글 키워드 추출 (영문 혼합 제거)
  function naverKeyword(title: string): string {
    const korean = (title.match(/[가-힣]+/g) ?? []).join(' ').trim();
    return korean.length >= 2 ? korean : title;
  }

  if (/^UC[\w-]{22}$/.test(keyword)) {
    creatorChannelId = keyword;
    // 채널명 조회
    const chData = await fetch(
      `${YT_BASE}/channels?part=snippet&id=${keyword}&key=${YT_KEY}`,
    ).then(r => r.json());
    searchKeyword = chData.items?.[0]?.snippet?.title ?? keyword;
  } else if (keyword.startsWith('@')) {
    const handleData = await fetch(
      `${YT_BASE}/channels?part=id,snippet&forHandle=${encodeURIComponent(keyword)}&key=${YT_KEY}`,
    ).then(r => r.json());
    creatorChannelId = handleData.items?.[0]?.id ?? '';
    searchKeyword   = handleData.items?.[0]?.snippet?.title ?? keyword;
  } else {
    const channelSearchData = await fetch(
      `${YT_BASE}/search?part=snippet&q=${encodeURIComponent(keyword)}&type=channel&maxResults=1&key=${YT_KEY}`,
    ).then(r => r.json());
    creatorChannelId = channelSearchData.items?.[0]?.snippet?.channelId ?? '';
    searchKeyword    = channelSearchData.items?.[0]?.snippet?.title ?? keyword;
  }

  // ════════════════════════════════════════════════════════════════════════════
  // STEP 2 — 병렬: 논란 영상 검색 + 크리에이터 영상 + Naver DataLab (200유닛)
  //   · YouTube: "keyword 논란" 검색 → 실제 위기 콘텐츠만 수집
  //   · DataLab: 기본 키워드 + 논란 키워드 그룹 동시 조회
  // ════════════════════════════════════════════════════════════════════════════
  const today      = refDate;
  const oneYearAgo = new Date(refTs - 365 * 864e5).toISOString().slice(0, 10);
  const sevenDaysAgoTs = refTs - 7 * 864e5;

  const naverKw = nameParam || naverKeyword(searchKeyword);
  const controversyQuery = `${naverKw} 논란`;
  // YouTube 시간 범위: 기준일 이전 전체 기간 (pubBefore만 사용)
  const pubBefore = encodeURIComponent(new Date(refDate + 'T23:59:59Z').toISOString());

  const [controversySearchData, creatorSearchData, trendData, googleTrendData] = await Promise.all([
    // 논란 키워드 특화 제3자 영상 (harmfulContentExposure) — 전체 기간
    fetch(
      `${YT_BASE}/search?part=snippet&q=${encodeURIComponent(controversyQuery)}&type=video&maxResults=20&order=relevance&regionCode=KR&relevanceLanguage=ko&key=${YT_KEY}`,
    ).then(r => r.json()),
    // 크리에이터 본인 영상: uploads 플레이리스트 (search API가 일부 채널에서 0 반환하는 문제 우회)
    creatorChannelId
      ? fetch(
          `${YT_BASE}/playlistItems?part=snippet&playlistId=UU${creatorChannelId.slice(2)}&maxResults=20&key=${YT_KEY}`,
        ).then(r => r.json())
      : Promise.resolve({ items: [] }),
    // DataLab: 1년치 일별 데이터 — Z-score 베이스라인 확보 (노트북 방식)
    fetch(`${NAVER_BASE}/datalab/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Naver-Client-Id': NAVER_ID, 'X-Naver-Client-Secret': NAVER_SECRET,
      },
      body: JSON.stringify({
        startDate: oneYearAgo, endDate: today, timeUnit: 'week',
        keywordGroups: [
          { groupName: 'base',        keywords: [naverKw] },
          { groupName: 'controversy', keywords: [`${naverKw} 논란`, `${naverKw} 사건`, `${naverKw} 협박`] },
        ],
      }),
    }).then(r => r.json()),
    // Google Trends: 비공식 API (실패 시 빈 배열 → Naver만 사용)
    fetchGoogleTrends(naverKw, oneYearAgo, today),
  ]);

  // 제3자 논란 영상 — 본인 채널 제외 후, 제목 or 자막에 크리에이터 이름 포함 여부로 관련성 검증
  const thirdPartyCandidates = (controversySearchData.items ?? [])
    .filter((i: { snippet: { channelId: string } }) =>
      !creatorChannelId || i.snippet.channelId !== creatorChannelId)
    .map((i: { id: { videoId: string }; snippet: { title: string } }) => ({
      videoId: i.id.videoId,
      title:   i.snippet.title as string,
    }));

  // 제목 포함 → 즉시 통과 / 미포함 → 자막에서 재확인 (Shorts는 자막 없으므로 자동 제외)
  const relevanceResults = await Promise.all(
    thirdPartyCandidates.map(async ({ videoId, title }: { videoId: string; title: string }) => {
      if (title.includes(naverKw)) return true;
      const transcript = await fetchTranscript(videoId);
      return transcript.includes(naverKw);
    }),
  );

  const thirdPartyIds: string[] = thirdPartyCandidates
    .filter((_: unknown, idx: number) => relevanceResults[idx])
    .map((v: { videoId: string }) => v.videoId);

  // 크리에이터 영상 ID (playlistItems → resourceId.videoId)
  const creatorVideoIds: string[] = (creatorSearchData.items ?? [])
    .map((i: { snippet: { resourceId?: { videoId: string } } }) =>
      i.snippet.resourceId?.videoId ?? '')
    .filter(Boolean)
    .slice(0, 10);

  // ── searchSpike: 노트북 방식 주간 rolling 13주 Z-score ──────────────────
  const baseTrend        = (trendData.results?.[0]?.data ?? []) as { period: string; ratio: number }[];
  const controversyTrend = (trendData.results?.[1]?.data ?? []) as { period: string; ratio: number }[];

  const bVals = baseTrend.map(p => p.ratio);
  const cVals = controversyTrend.map(p => p.ratio);

  // rolling 13주 window: 직전 13개 주간값으로 mean/std 계산 후 최근 주 Z-score
  function rollingZ(values: number[], window = 13): number {
    if (values.length < window + 1) return 0;
    const recent   = values[values.length - 1];
    const baseline = values.slice(-(window + 1), -1);
    const bMean    = mean(baseline);
    const bStd     = std(baseline);
    return bStd > 0 ? Math.max(0, (recent - bMean) / bStd) : 0;
  }

  const baseZ        = rollingZ(bVals);
  const controversyZ = rollingZ(cVals);
  const googleZ      = rollingZ(googleTrendData);

  // Naver 단독 / Google 추가 시 75:25 블렌딩 (Google 실패 → 빈 배열 → googleZ=0 → Naver 100%)
  const naverCombinedZ = controversyZ * 0.75 + baseZ * 0.25;
  const combinedZ = googleTrendData.length > 0
    ? naverCombinedZ * 0.75 + googleZ * 0.25
    : naverCombinedZ;

  // 노트북 방식 레벨 시스템: Level3(Z≥4)→100, Level2(Z≥2)→75, Level1(Z≥1)→25, Level0→비례
  const searchSpikeScore =
    combinedZ >= 4 ? 100 :   // Level 3 → weight×100 = +20점
    combinedZ >= 2 ? 75  :   // Level 2 → weight×75  = +15점
    combinedZ >= 1 ? 25  :   // Level 1 → weight×25  = +5점
    Math.min(20, combinedZ * 20);  // Level 0
  const searchSpikeLevel = combinedZ >= 4 ? 3 : combinedZ >= 2 ? 2 : combinedZ >= 1 ? 1 : 0;

  // ════════════════════════════════════════════════════════════════════════════
  // STEP 3 — 병렬: 영상 통계 2건 (2 유닛)
  // ════════════════════════════════════════════════════════════════════════════
  const [thirdPartyStatsData, creatorStatsData, channelStatsData] = await Promise.all([
    thirdPartyIds.length
      ? fetch(`${YT_BASE}/videos?part=statistics&id=${thirdPartyIds.join(',')}&key=${YT_KEY}`).then(r => r.json())
      : Promise.resolve({ items: [] }),
    creatorVideoIds.length
      ? fetch(`${YT_BASE}/videos?part=snippet,statistics,contentDetails&id=${creatorVideoIds.join(',')}&key=${YT_KEY}`).then(r => r.json())
      : Promise.resolve({ items: [] }),
    // 채널 전체 통계: totalViews / videoCount → 노트북 방식 baseline
    creatorChannelId
      ? fetch(`${YT_BASE}/channels?part=statistics&id=${creatorChannelId}&key=${YT_KEY}`).then(r => r.json())
      : Promise.resolve({ items: [] }),
  ]);

  // 제3자 총 조회수
  const totalViews = (thirdPartyStatsData.items ?? []).reduce(
    (s: number, v: { statistics: { viewCount?: string } }) => s + parseInt(v.statistics.viewCount ?? '0'), 0,
  );

  // 크리에이터 영상: Shorts 제외 (EDS/CAV 계산용)
  const creatorVideos = (creatorStatsData.items ?? []).filter(
    (v: { contentDetails: { duration: string } }) => durationToSec(v.contentDetails?.duration ?? '') > 60,
  );

  // ── HCE: 노트북 방식 — 채널 전체 평균 조회수를 baseline으로 사용 ──────────
  // 노트북: youtube_tzuyang_full.csv 전체 영상 평균 → 채널 통계 API로 대체
  const chStats = channelStatsData.items?.[0]?.statistics;
  const chTotalViews = parseInt(chStats?.viewCount ?? '0');
  const chVideoCount = parseInt(chStats?.videoCount ?? '0');
  const ownAvgViews  = chVideoCount > 0 ? chTotalViews / chVideoCount : 0;
  const hceScore = Math.min(100, ownAvgViews > 0 ? (totalViews / ownAvgViews) * 10 : 0);

  // ── 경제 신호: 조회수 변화율 + 업로드 공백 ──────────────────────────────
  let viewDropRate = 0, uploadGapDays = 0, recentAvgViews = 0, prevAvgViews = 0;

  if (creatorVideos.length > 0) {
    uploadGapDays = Math.floor(
      (Date.now() - new Date(creatorVideos[0].snippet.publishedAt).getTime()) / 864e5,
    );
    const viewCounts: number[] = creatorVideos
      .map((v: { statistics: { viewCount?: string } }) => parseInt(v.statistics.viewCount ?? '0'))
      .filter((v: number) => v > 0);

    if (viewCounts.length >= 4) {
      recentAvgViews = mean(viewCounts.slice(0, 3));
      prevAvgViews   = mean(viewCounts.slice(3, 6));
      viewDropRate   = prevAvgViews > 0 ? Math.max(0, 1 - recentAvgViews / prevAvgViews) : 0;
    }
  }

  // ── comment velocity: comment_count / hours_since_upload (노트북 방식) ──
  const now = Date.now();
  const videoVelocities: number[] = creatorVideos
    .map((v: { snippet: { publishedAt: string }; statistics: { commentCount?: string } }) => {
      const hoursSince = (now - new Date(v.snippet.publishedAt).getTime()) / 3_600_000;
      const count      = parseInt(v.statistics.commentCount ?? '0');
      return hoursSince > 0 ? count / hoursSince : 0;
    })
    .filter((v: number) => v > 0);

  let commentVelocityZ = 0;
  if (videoVelocities.length >= 4) {
    const recentVel   = mean(videoVelocities.slice(0, 3));
    const baselineArr = videoVelocities.slice(3);
    const baselineMean = mean(baselineArr);
    const baselineStd  = std(baselineArr);
    commentVelocityZ = baselineStd > 0
      ? Math.max(0, (recentVel - baselineMean) / baselineStd)
      : Math.max(0, baselineMean > 0 ? recentVel / baselineMean - 1 : 0);
  }

  // ════════════════════════════════════════════════════════════════════════════
  // STEP 4 — 병렬: 댓글 수집 + 논란 뉴스 + 일반 블로그 (6유닛 + Naver 무료)
  // ════════════════════════════════════════════════════════════════════════════

  const [thirdPartyComments, creatorComments, controversyNewsData, blogData] = await Promise.all([
    fetchComments(thirdPartyIds.slice(0, 3), 100),
    fetchComments(creatorVideoIds.slice(0, 3), 100),
    // 뉴스: 논란 키워드로 검색 (위기 관련 기사만)
    fetch(
      `${NAVER_BASE}/search/news.json?query=${encodeURIComponent(controversyQuery)}&display=100&sort=date`,
      { headers: { 'X-Naver-Client-Id': NAVER_ID, 'X-Naver-Client-Secret': NAVER_SECRET } },
    ).then(r => r.json()),
    fetch(
      `${NAVER_BASE}/search/blog.json?query=${encodeURIComponent(naverKw)}&display=100&sort=date`,
      { headers: { 'X-Naver-Client-Id': NAVER_ID, 'X-Naver-Client-Secret': NAVER_SECRET } },
    ).then(r => r.json()),
  ]);

  // 논란 뉴스 최근 7일 (기준일 기준)
  const recentNewsCount = (controversyNewsData.items ?? []).filter(
    (item: { pubDate: string }) => {
      try { return new Date(item.pubDate).getTime() >= sevenDaysAgoTs; } catch { return false; }
    },
  ).length;

  // ── News: 노트북 방식 일별 Z-score × 20 ──────────────────────────────────
  const newsDateMap = new Map<string, number>();
  for (const item of controversyNewsData.items ?? []) {
    try {
      const d = new Date((item as { pubDate: string }).pubDate).toISOString().slice(0, 10);
      newsDateMap.set(d, (newsDateMap.get(d) ?? 0) + 1);
    } catch {}
  }
  const dailyCounts   = [...newsDateMap.values()];
  const newsDailyMean = mean(dailyCounts);
  const newsDailyStd  = std(dailyCounts);
  const newsZ         = newsDailyStd > 0
    ? Math.max(0, (recentNewsCount / 7 - newsDailyMean) / newsDailyStd)
    : 0;
  const newsSNSScore  = Math.min(100, newsZ * 20);

  // 블로그 최근 7일 (기준일 기준)
  const recentBlogCount = (blogData.items ?? []).filter(
    (item: { postdate: string }) => {
      try {
        const d = item.postdate ?? '';
        return new Date(`${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`).getTime() >= sevenDaysAgoTs;
      } catch { return false; }
    },
  ).length;

  // ── Manipulation Signal (노트북 4-factor) ─────────────────────────────────
  const suspiciousScore = calcManipulationScore(
    creatorComments.texts,
    creatorComments.authorCounts,
    creatorComments.publishedAts,
  );

  // ════════════════════════════════════════════════════════════════════════════
  // STEP 5 — 영상 기반 독성 분석 (노트북 방식: 제목+자막 키워드 + 감성)
  // ════════════════════════════════════════════════════════════════════════════
  const controversyVideos = (controversySearchData.items ?? [])
    .filter((i: { snippet: { channelId: string } }) =>
      !creatorChannelId || i.snippet.channelId !== creatorChannelId)
    .map((i: { id: { videoId: string }; snippet: { title: string } }) => ({
      videoId: i.id.videoId,
      title:   i.snippet.title as string,
    }));
  const toxicityScore = await analyzeVideoToxicity(controversyVideos);

  // ════════════════════════════════════════════════════════════════════════════
  // STEP 6 — DRI 계산
  // ════════════════════════════════════════════════════════════════════════════
  const raw: RawSignalData = {
    searchTrendPeak:        searchSpikeScore,
    commentVelocityZ,
    toxicityRate:           0,
    negativeStanceRate:     0,
    duplicateRate:          duplicateRate(thirdPartyComments.texts),
    relatedVideoCount:      thirdPartyIds.length,
    totalExposureViews:     totalViews,
    newsCount:              recentNewsCount,
    snsCount:               0,
    blogCount:              recentBlogCount,
    suspiciousPatternScore: suspiciousScore,
    viewDropRate,
    uploadGapDays,
    searchSpikeScore,
    hceScore,
    newsSNSScore,
    toxicityScore,
  };

  const signals = rawToSignals(raw);
  const result  = calculateDRI(signals);

  // 90일 트렌드 시계열 (DataLab 결과 — 1년 중 최근 90일만 표시)
  const trendSeries = baseTrend.slice(-90).map(
    (point: { period: string; ratio: number }, i: number) => {
      const offset = Math.max(0, baseTrend.length - 90) + i;
      return {
        date:             point.period,
        baseRatio:        point.ratio,
        controversyRatio: (controversyTrend[offset] as { period: string; ratio: number } | undefined)?.ratio ?? 0,
      };
    },
  );

  return NextResponse.json({
    ...result,
    trendSeries,
    meta: {
      thirdPartyVideoCount:    thirdPartyIds.length,
      totalExposureViews:      totalViews,
      ownAvgViews:             Math.round(ownAvgViews),
      chTotalViews:            chTotalViews,
      chVideoCount:            chVideoCount,
      hceScore:                Math.round(hceScore * 10) / 10,
      recentControversyNews:   recentNewsCount,
      recentBlogCount,
      searchSpikeScore:        Math.round(searchSpikeScore * 10) / 10,
      searchSpikeLevel,
      combinedZ:               Math.round(combinedZ * 100) / 100,
      naverCombinedZ:          Math.round(naverCombinedZ * 100) / 100,
      googleZ:                 Math.round(googleZ * 100) / 100,
      googleDataPoints:        googleTrendData.length,
      baseZ:                   Math.round(baseZ * 100) / 100,
      controversyZ:            Math.round(controversyZ * 100) / 100,
      newsZ:                   Math.round(newsZ * 100) / 100,
      newsSNSScore:            Math.round(newsSNSScore * 10) / 10,
      toxicityScore:           Math.round(toxicityScore * 10) / 10,
      commentCount:            thirdPartyComments.texts.length,
      suspiciousPatternScore:  Math.round(suspiciousScore),
      viewDropRate:            Math.round(viewDropRate * 100) / 100,
      uploadGapDays,
      recentAvgViews:          Math.round(recentAvgViews),
      prevAvgViews:            Math.round(prevAvgViews),
      commentVelocityZ:        Math.round(commentVelocityZ * 100) / 100,
      creatorChannelId,
    },
  });
}
