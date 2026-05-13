'use client';

import { useState } from 'react';
import type { IncidentSnapshot } from '../types';
import SectionCard from './shared/SectionCard';
import { formatViews, formatDateTime } from '../utils/format';

const STAGE_COLOR: Record<string, string> = {
  Normal:  'bg-teal-50  text-teal-700  border-teal-200',
  Watch:   'bg-amber-50 text-amber-700 border-amber-200',
  Alert:   'bg-orange-50 text-orange-700 border-orange-200',
  Trigger: 'bg-rose-50  text-rose-700  border-rose-200',
  Severe:  'bg-rose-100 text-rose-800  border-rose-300',
};

function downloadSnapshot(snap: IncidentSnapshot) {
  const payload = {
    savedAt: snap.savedAt,
    driScore: snap.driScore,
    driStage: snap.driStage,
    signals: snap.signals,
    relatedVideos: snap.relatedVideos,
    totalExposureViews: snap.totalExposureViews,
    toxicityRate: snap.toxicityRate,
    riskUrls: snap.riskUrls,
    evidencePreserved: snap.evidencePreserved,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `snapshot_DRI${snap.driScore}_${snap.savedAt.slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

interface Props {
  snapshots: IncidentSnapshot[];
}

export default function SnapshotHistory({ snapshots }: Props) {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  return (
    <SectionCard title="사고 스냅샷 히스토리" badge={`${snapshots.length}건`} badgeColor="bg-slate-500">
      {snapshots.length === 0 ? (
        <p className="text-sm text-slate-500 py-2">저장된 스냅샷이 없습니다.</p>
      ) : (
        <div className="space-y-2">
          {snapshots.map((snap, i) => {
            const stageCls = STAGE_COLOR[snap.driStage] ?? STAGE_COLOR.Normal;
            const isOpen = openIdx === i;
            return (
              <div key={snap.savedAt} className="border border-slate-200 rounded-lg overflow-hidden">
                {/* 행 헤더 */}
                <button
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors"
                  onClick={() => setOpenIdx(isOpen ? null : i)}
                >
                  <span className="text-xs text-slate-400 w-4 flex-shrink-0">{i + 1}</span>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 ${stageCls}`}>
                    {snap.driStage}
                  </span>
                  <span className="text-sm font-bold text-slate-800">DRI {snap.driScore}점</span>
                  <span className="text-xs text-slate-400 flex-1">{formatDateTime(snap.savedAt)}</span>
                  <span className={`text-xs flex-shrink-0 ${snap.evidencePreserved ? 'text-teal-600' : 'text-slate-400'}`}>
                    {snap.evidencePreserved ? '📁 증거보존' : '증거 미보존'}
                  </span>
                  <span className="text-slate-400 text-xs ml-1">{isOpen ? '▲' : '▼'}</span>
                </button>

                {/* 상세 펼침 */}
                {isOpen && (
                  <div className="px-4 pb-4 pt-1 border-t border-slate-100 space-y-4">
                    {/* 주요 수치 */}
                    <div className="grid grid-cols-3 gap-2">
                      <DetailStat label="관련 영상" value={`${snap.relatedVideos}개`} />
                      <DetailStat label="총 노출" value={formatViews(snap.totalExposureViews)} />
                      <DetailStat label="독성 댓글" value={`${(snap.toxicityRate * 100).toFixed(0)}%`} />
                    </div>

                    {/* DRI 신호 */}
                    <div>
                      <p className="text-xs text-slate-500 mb-2">DRI 구성요소</p>
                      <div className="space-y-1.5">
                        {Object.entries(snap.signals).map(([key, val]) => (
                          <div key={key} className="flex items-center gap-2">
                            <span className="text-xs text-slate-500 w-44 flex-shrink-0">{SIGNAL_LABELS[key] ?? key}</span>
                            <div className="flex-1 bg-slate-100 rounded-full h-1.5">
                              <div
                                className={`h-1.5 rounded-full ${val >= 75 ? 'bg-rose-400' : val >= 50 ? 'bg-amber-400' : 'bg-teal-400'}`}
                                style={{ width: `${val}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-600 w-6 text-right">{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* 위험 URL */}
                    {snap.riskUrls.length > 0 && (
                      <div>
                        <p className="text-xs text-slate-500 mb-1">저장된 위험 URL</p>
                        <ul className="space-y-0.5">
                          {snap.riskUrls.map((url, j) => (
                            <li key={j} className="text-xs text-sky-600 truncate">{url}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* 다운로드 */}
                    <button
                      onClick={() => downloadSnapshot(snap)}
                      className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-50 transition-colors"
                    >
                      ↓ 스냅샷 다운로드 (JSON)
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3 text-center">
      <div className="text-sm font-semibold text-slate-800">{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

const SIGNAL_LABELS: Record<string, string> = {
  searchSpike:              'Search Spike',
  commentAttackVelocity:    'Comment Attack Velocity',
  toxicityDuplication:      'Toxicity & Duplication',
  harmfulContentExposure:   'Harmful Content Exposure',
  newsSNSAmplification:     'News/SNS Amplification',
  manipulationSignal:       'Manipulation Signal',
  economicDisruptionSignal: 'Economic Disruption Signal',
};
