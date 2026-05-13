'use client';

import type { ProactiveMonitoringData } from '../types';
import SectionCard from './shared/SectionCard';

const STATUS_CONFIG = {
  active:  { dot: 'bg-teal-400',   text: 'text-teal-600',  bg: 'bg-teal-50',  border: 'border-teal-200',  label: '정상' },
  warning: { dot: 'bg-amber-400',  text: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200', label: '감지' },
  idle:    { dot: 'bg-slate-300',  text: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200', label: '대기' },
};

interface Props {
  data: ProactiveMonitoringData;
}

function barColor(score: number): string {
  if (score >= 75) return 'bg-rose-400';
  if (score >= 60) return 'bg-amber-400';
  if (score >= 40) return 'bg-yellow-300';
  return 'bg-teal-400';
}

export default function ProactiveMonitoring({ data }: Props) {
  const maxScore = Math.max(...data.driTrend.map((p) => p.score), 1);

  return (
    <div className="space-y-4">
      <SectionCard title="실시간 감시 현황">
        <div className="grid grid-cols-2 gap-2">
          {data.channels.map((ch) => {
            const cfg = STATUS_CONFIG[ch.status];
            return (
              <div key={ch.label} className={`rounded-lg border ${cfg.border} ${cfg.bg} px-3 py-2.5`}>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot} ${ch.status === 'active' ? 'animate-pulse' : ''}`} />
                  <span className="text-xs text-slate-600 font-medium truncate">{ch.label}</span>
                </div>
                <div className="flex items-end justify-between">
                  <span className={`text-lg font-bold ${cfg.text}`}>{ch.count.toLocaleString()}</span>
                  <span className={`text-xs font-semibold ${cfg.text}`}>{cfg.label}</span>
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {new Date(ch.lastChecked).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })} 기준
                </div>
              </div>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard title="DRI 7일 추이">
        <div className="flex items-end gap-1.5 h-20">
          {data.driTrend.map((point) => {
            const height = Math.max((point.score / maxScore) * 100, 4);
            const color = barColor(point.score);
            const isLatest = point === data.driTrend[data.driTrend.length - 1];
            return (
              <div key={point.date} className="flex-1 flex flex-col items-center gap-1 group relative">
                {isLatest && (
                  <span className="absolute -top-5 text-xs font-bold text-rose-500">{point.score}</span>
                )}
                <div className="w-full flex items-end justify-center" style={{ height: '64px' }}>
                  <div
                    className={`w-full rounded-t ${color} ${isLatest ? 'ring-2 ring-offset-1 ring-rose-300' : ''}`}
                    style={{ height: `${height}%` }}
                  />
                </div>
                <span className="text-xs text-slate-400">{point.date}</span>
              </div>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard title="증거 보관함">
        <div className="grid grid-cols-3 gap-3 text-center">
          <VaultStat label="저장된 URL" value={data.evidenceVault.savedUrls.toString()} />
          <VaultStat label="자동 스냅샷" value={data.evidenceVault.autoSnapshots.toString()} />
          <VaultStat
            label="마지막 저장"
            value={new Date(data.evidenceVault.lastSavedAt).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
          />
        </div>
      </SectionCard>

      <SectionCard title="사전 준비 체크리스트">
        <div className="space-y-2.5">
          {data.readiness.map((item, i) => (
            <div key={i} className="flex items-start gap-2.5">
              <span className={`flex-shrink-0 w-4 h-4 mt-0.5 rounded-full flex items-center justify-center text-xs
                ${item.done ? 'bg-teal-100 text-teal-600' : 'bg-slate-100 text-slate-400'}`}>
                {item.done ? '✓' : '·'}
              </span>
              <div>
                <span className={`text-sm ${item.done ? 'text-slate-700' : 'text-slate-600'}`}>{item.label}</span>
                {!item.done && item.action && (
                  <p className="text-xs text-amber-600 mt-0.5">{item.action}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

function VaultStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 rounded-lg py-3">
      <div className="text-slate-800 font-bold text-lg">{value}</div>
      <div className="text-slate-500 text-xs mt-0.5">{label}</div>
    </div>
  );
}
