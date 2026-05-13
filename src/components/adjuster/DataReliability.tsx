'use client';

import type { DataReliabilityItem } from '../../types';
import SectionCard from '../shared/SectionCard';

const RELIABILITY_CONFIG = {
  high:   { label: '높음', color: 'text-teal-600',  bg: 'bg-teal-50',   border: 'border-teal-200' },
  medium: { label: '중간', color: 'text-amber-600', bg: 'bg-amber-50',  border: 'border-amber-200' },
  low:    { label: '낮음', color: 'text-rose-600',  bg: 'bg-rose-50',   border: 'border-rose-200' },
};

interface Props { items: DataReliabilityItem[] }

export default function DataReliability({ items }: Props) {
  return (
    <SectionCard title="데이터 신뢰도">
      <div className="space-y-2">
        {items.map((item, i) => {
          const cfg = RELIABILITY_CONFIG[item.reliability];
          return (
            <div key={i} className={`rounded-lg border ${cfg.border} ${cfg.bg} px-4 py-3 flex items-start justify-between gap-3`}>
              <div>
                <div className="text-sm text-slate-700">{item.source}</div>
                <div className="text-xs text-slate-600 mt-0.5">{item.reason}</div>
              </div>
              <span className={`text-xs font-semibold flex-shrink-0 ${cfg.color}`}>{cfg.label}</span>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
