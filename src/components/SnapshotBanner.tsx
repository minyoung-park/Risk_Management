'use client';

import type { IncidentSnapshot } from '../types';
import SectionCard from './shared/SectionCard';

interface Props {
  snapshot: IncidentSnapshot;
  onDismiss: () => void;
}

export default function SnapshotBanner({ snapshot, onDismiss }: Props) {
  const savedTime = new Date(snapshot.savedAt).toLocaleString('ko-KR');

  return (
    <SectionCard title="자동 저장된 사고 스냅샷" badge="Trigger 초과" badgeColor="bg-rose-900/60">
      <div className="bg-rose-950/20 border border-rose-900/40 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 text-rose-300/90 text-sm">
          <span>●</span>
          <span>Trigger 기준 초과 — 현재 모니터링 상태가 사고 스냅샷으로 자동 저장되었습니다.</span>
        </div>
        <div className="text-xs text-slate-600 mt-1">저장 시각: {savedTime}</div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 text-sm">
        <SnapStat label="DRI 점수" value={`${snapshot.driScore}점`} />
        <SnapStat label="단계" value={snapshot.driStage} />
        <SnapStat label="관련 영상" value={`${snapshot.relatedVideos}개`} />
        <SnapStat label="총 노출" value={formatViews(snapshot.totalExposureViews)} />
        <SnapStat label="독성 댓글" value={`${(snapshot.toxicityRate * 100).toFixed(0)}%`} />
        <SnapStat label="증거보존" value={snapshot.evidencePreserved ? '완료' : '미완료'} valueColor={snapshot.evidencePreserved ? 'text-teal-300' : 'text-rose-300'} />
      </div>

      {snapshot.riskUrls.length > 0 && (
        <div className="mt-4">
          <div className="text-xs text-slate-600 mb-1.5">주요 위험 URL</div>
          <ul className="space-y-1">
            {snapshot.riskUrls.map((url, i) => (
              <li key={i} className="text-xs text-sky-400/70 truncate">{url}</li>
            ))}
          </ul>
        </div>
      )}

      <button onClick={onDismiss} className="mt-4 text-xs text-slate-600 hover:text-gray-400 underline">
        알림 닫기
      </button>
    </SectionCard>
  );
}

function SnapStat({ label, value, valueColor = 'text-slate-800' }: { label: string; value: string; valueColor?: string }) {
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
      <div className="text-xs text-slate-600">{label}</div>
      <div className={`font-semibold mt-0.5 ${valueColor}`}>{value}</div>
    </div>
  );
}

function formatViews(n: number): string {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(0)}만`;
  return n.toLocaleString();
}
