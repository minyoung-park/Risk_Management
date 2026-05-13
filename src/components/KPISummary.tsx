'use client';

import type { DRIResult } from '../types';
import { formatViews, formatTime } from '../utils/format';

const STAGE_CONFIG = {
  Normal:  { color: 'text-teal-700',   bg: 'bg-teal-50',   border: 'border-teal-200',  label: '정상' },
  Watch:   { color: 'text-amber-700',  bg: 'bg-amber-50',  border: 'border-amber-200', label: '주의' },
  Alert:   { color: 'text-orange-700', bg: 'bg-orange-50', border: 'border-orange-200',label: '경보' },
  Trigger: { color: 'text-rose-700',   bg: 'bg-rose-50',   border: 'border-rose-200',  label: '트리거' },
  Severe:  { color: 'text-rose-800',   bg: 'bg-rose-100',  border: 'border-rose-300',  label: '긴급' },
};

interface Props {
  dri: DRIResult;
  relatedVideos: number;
  totalExposureViews: number;
  lastUpdated: string;
}

export default function KPISummary({ dri, relatedVideos, totalExposureViews, lastUpdated }: Props) {
  const cfg = STAGE_CONFIG[dri.stage];

  return (
    <div className={`rounded-xl border ${cfg.border} ${cfg.bg} p-6`}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className={`text-6xl font-black ${cfg.color}`}>{dri.score}</div>
            <div className="text-slate-500 text-xs mt-1">DRI 점수</div>
          </div>
          <div>
            <div className={`text-2xl font-bold ${cfg.color}`}>{dri.stage}</div>
            <div className="text-slate-600 text-sm">{cfg.label} 단계</div>
            <div className="text-slate-500 text-xs mt-1">기준: 75점 초과 시 Trigger</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <KPICard label="관련 영상" value={`${relatedVideos}개`} />
          <KPICard label="총 노출 조회수" value={formatViews(totalExposureViews)} />
          <KPICard
            label="마지막 업데이트"
            value={formatTime(lastUpdated)}
          />
        </div>
      </div>

      {(dri.stage === 'Trigger' || dri.stage === 'Severe') && (
        <div className="mt-4 flex items-center gap-2 text-sm text-rose-700 bg-rose-100 border border-rose-200 rounded-lg px-4 py-2">
          <span>⚠</span>
          <span>보험 트리거 기준(75점)을 초과했습니다. 즉각적인 대응 조치가 필요합니다.</span>
        </div>
      )}
    </div>
  );
}

function KPICard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/60 border border-white/80 rounded-lg px-4 py-3 text-center">
      <div className="text-slate-800 font-semibold text-lg">{value}</div>
      <div className="text-slate-500 text-xs mt-0.5">{label}</div>
    </div>
  );
}

