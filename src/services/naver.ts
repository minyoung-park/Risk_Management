// Naver DataLab(검색량) + Search API(뉴스·블로그·웹문서) 서비스
// USE_MOCK=false + 환경변수 설정 시 실제 API 호출
// Naver API는 서버사이드에서만 호출 가능(CORS) → Next.js API Route(/api/naver/*)로 프록시 필요

import { USE_MOCK } from '../config';

export interface SearchTrendPoint {
  period: string; // 'YYYY-MM-DD'
  ratio: number;  // 0~100
}

export interface NaverNewsItem {
  title: string;
  link: string;
  description: string;
  pubDate: string;
}

// ─── Mock 데이터 ──────────────────────────────────────────────────────────────

const MOCK_TREND: SearchTrendPoint[] = [
  { period: '2025-08-07', ratio: 8 },
  { period: '2025-08-08', ratio: 9 },
  { period: '2025-08-09', ratio: 7 },
  { period: '2025-08-10', ratio: 11 },
  { period: '2025-08-11', ratio: 14 },
  { period: '2025-08-12', ratio: 22 },
  { period: '2025-08-13', ratio: 100 },
  { period: '2025-08-14', ratio: 87 },
];

const MOCK_NEWS: NaverNewsItem[] = [
  { title: '유튜버 김재민 논란...팬들 충격', link: '#', description: '...', pubDate: 'Wed, 13 Aug 2025 18:00:00 +0900' },
];

// ─── 공개 API ────────────────────────────────────────────────────────────────

export async function fetchSearchTrend(keyword: string): Promise<SearchTrendPoint[]> {
  if (USE_MOCK) return MOCK_TREND;
  // 실제 호출: /api/naver/datalab 프록시 사용
  const res = await fetch('/api/naver/datalab', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword }),
  });
  return res.json();
}

export async function fetchNewsCount(keyword: string): Promise<NaverNewsItem[]> {
  if (USE_MOCK) return MOCK_NEWS;
  const res = await fetch(`/api/naver/news?query=${encodeURIComponent(keyword)}`);
  return res.json();
}

export async function fetchBlogCount(keyword: string): Promise<number> {
  if (USE_MOCK) return 142;
  const res = await fetch(`/api/naver/blog?query=${encodeURIComponent(keyword)}`);
  const data = await res.json();
  return data.total ?? 0;
}
