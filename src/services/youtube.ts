// YouTube Data API v3 서비스
// USE_MOCK=true 일 때는 mockData를 반환
// USE_MOCK=false 로 바꾸고 YOUTUBE_API_KEY 환경변수를 설정하면 실제 API 호출

const USE_MOCK = true;
const API_KEY = process.env.NEXT_PUBLIC_YOUTUBE_API_KEY ?? '';
const BASE_URL = 'https://www.googleapis.com/youtube/v3';

export interface YouTubeVideo {
  videoId: string;
  title: string;
  channelName: string;
  publishedAt: string;
  viewCount: number;
  commentCount: number;
  url: string;
}

export interface YouTubeComment {
  commentId: string;
  text: string;
  authorId: string;
  publishedAt: string;
  likeCount: number;
}

// ─── Mock 데이터 ──────────────────────────────────────────────────────────────

const MOCK_VIDEOS: YouTubeVideo[] = [
  { videoId: 'v001', title: '[긴급] 김재민 진짜 논란 정리', channelName: '렉카TV', publishedAt: '2025-08-13T14:22:00Z', viewCount: 4_200_000, commentCount: 18_400, url: 'https://youtube.com/watch?v=v001' },
  { videoId: 'v002', title: '김재민 사건 팩트체크', channelName: '이슈분석소', publishedAt: '2025-08-13T16:05:00Z', viewCount: 2_800_000, commentCount: 9_200, url: 'https://youtube.com/watch?v=v002' },
  { videoId: 'v003', title: '김재민 반응모음 총정리', channelName: '리액션월드', publishedAt: '2025-08-14T01:30:00Z', viewCount: 1_100_000, commentCount: 4_100, url: 'https://youtube.com/watch?v=v003' },
];

const MOCK_COMMENTS: YouTubeComment[] = [
  { commentId: 'c001', text: '완전 실망이다 구독 취소함', authorId: 'user_hash_001', publishedAt: '2025-08-13T15:00:00Z', likeCount: 3_200 },
  { commentId: 'c002', text: '이건 진짜 해명해야 되는 거 아님?', authorId: 'user_hash_002', publishedAt: '2025-08-13T15:10:00Z', likeCount: 2_100 },
  { commentId: 'c003', text: '역시 믿었는데 배신감 든다', authorId: 'user_hash_003', publishedAt: '2025-08-13T15:20:00Z', likeCount: 1_800 },
];

// ─── 공개 API ────────────────────────────────────────────────────────────────

export async function searchRelatedVideos(keyword: string): Promise<YouTubeVideo[]> {
  if (USE_MOCK) return MOCK_VIDEOS;

  const res = await fetch(
    `${BASE_URL}/search?part=snippet&q=${encodeURIComponent(keyword)}&type=video&maxResults=50&key=${API_KEY}`
  );
  const data = await res.json();
  return data.items.map((item: any) => ({
    videoId: item.id.videoId,
    title: item.snippet.title,
    channelName: item.snippet.channelTitle,
    publishedAt: item.snippet.publishedAt,
    viewCount: 0,
    commentCount: 0,
    url: `https://youtube.com/watch?v=${item.id.videoId}`,
  }));
}

export async function fetchVideoStats(videoIds: string[]): Promise<YouTubeVideo[]> {
  if (USE_MOCK) return MOCK_VIDEOS;

  const ids = videoIds.join(',');
  const res = await fetch(
    `${BASE_URL}/videos?part=snippet,statistics&id=${ids}&key=${API_KEY}`
  );
  const data = await res.json();
  return data.items.map((item: any) => ({
    videoId: item.id,
    title: item.snippet.title,
    channelName: item.snippet.channelTitle,
    publishedAt: item.snippet.publishedAt,
    viewCount: parseInt(item.statistics.viewCount ?? '0'),
    commentCount: parseInt(item.statistics.commentCount ?? '0'),
    url: `https://youtube.com/watch?v=${item.id}`,
  }));
}

export async function fetchComments(videoId: string): Promise<YouTubeComment[]> {
  if (USE_MOCK) return MOCK_COMMENTS;

  const res = await fetch(
    `${BASE_URL}/commentThreads?part=snippet&videoId=${videoId}&maxResults=100&key=${API_KEY}`
  );
  const data = await res.json();
  return data.items.map((item: any) => ({
    commentId: item.id,
    text: item.snippet.topLevelComment.snippet.textDisplay,
    authorId: item.snippet.topLevelComment.snippet.authorChannelId?.value ?? 'unknown',
    publishedAt: item.snippet.topLevelComment.snippet.publishedAt,
    likeCount: item.snippet.topLevelComment.snippet.likeCount,
  }));
}
