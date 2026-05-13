'use client';

import { useState } from 'react';
import type { RelatedVideo } from '../types';
import SectionCard from './shared/SectionCard';
import { formatViews, formatShortDate } from '../utils/format';

interface Props {
  videos: RelatedVideo[];
  totalCount: number;
}

export default function RelatedVideosList({ videos, totalCount }: Props) {
  const [open, setOpen] = useState(false);

  const cyberjackerCount = videos.filter((v) => v.isCyberjacker).length;

  return (
    <SectionCard title="관련 영상 목록">
      {/* 요약 헤더 + 토글 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-semibold text-slate-800">총 {totalCount}개</span>
          <span className="text-slate-400">·</span>
          <span className="text-rose-500 text-xs font-medium">사이버렉카 {cyberjackerCount}개 포함</span>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
        >
          {open ? '목록 닫기 ▲' : '목록 보기 ▼'}
        </button>
      </div>

      {open && (
        <div className="mt-4">
          <div className="divide-y divide-slate-100">
            {videos.map((video, i) => (
              <div key={video.videoId} className="flex items-center gap-3 py-2.5 group">
                {/* 순위 */}
                <span className="w-5 text-xs text-slate-400 text-right flex-shrink-0">{i + 1}</span>

                {/* 렉카 뱃지 */}
                {video.isCyberjacker
                  ? <span className="text-xs px-1.5 py-0.5 bg-rose-50 text-rose-500 border border-rose-200 rounded flex-shrink-0">렉카</span>
                  : <span className="w-[38px] flex-shrink-0" />
                }

                {/* 제목 */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-700 truncate">{video.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{video.channelName} · {formatShortDate(video.publishedAt)}</p>
                </div>

                {/* 조회수 */}
                <span className="text-xs text-slate-500 flex-shrink-0 tabular-nums">
                  {formatViews(video.viewCount)}
                </span>
              </div>
            ))}
          </div>

          {totalCount > videos.length && (
            <p className="mt-3 text-xs text-slate-400 text-center">
              상위 {videos.length}개 표시 중 · 전체 {totalCount}개
            </p>
          )}
        </div>
      )}
    </SectionCard>
  );
}

