'use client';

import type { CoverageItem } from '../types';
import SectionCard from './shared/SectionCard';

const APPLICABILITY_CONFIG = {
  '높음':  { color: 'text-rose-600',   bg: 'bg-rose-50',    border: 'border-rose-200' },
  '중간':  { color: 'text-amber-600',  bg: 'bg-amber-50',   border: 'border-amber-200' },
  '낮음':  { color: 'text-slate-600',  bg: 'bg-slate-50',   border: 'border-slate-200' },
  '보류':  { color: 'text-sky-600',    bg: 'bg-sky-50',     border: 'border-sky-200' },
};

function formatRange(item: CoverageItem): string {
  if (item.rangeMin === null) return '현재 산정 제외';
  if (item.requiresAdditionalDocs && item.rangeMax === null) return '추가자료 필요';
  if (item.rangeMin === 0 && item.rangeMax !== null)
    return `0 ~ ${(item.rangeMax / 10000).toFixed(0)}만 원`;
  return `${(item.rangeMin! / 10000).toFixed(0)}만 ~ ${(item.rangeMax! / 10000).toFixed(0)}만 원`;
}

interface Props { coverages: CoverageItem[] }

export default function CoveragePanel({ coverages }: Props) {
  return (
    <SectionCard title="담보별 예상 보장 가능 범위">
      <p className="text-xs text-gray-600 mb-3">
        ※ 확정 보험금이 아닌 <span className="text-slate-600">추정 지급 범위</span>입니다. 실제 보험금은 손해사정 후 결정됩니다.
      </p>
      <div className="space-y-2.5">
        {coverages.map((item) => {
          const cfg = APPLICABILITY_CONFIG[item.applicability];
          return (
            <div key={item.id} className={`rounded-lg border ${cfg.border} ${cfg.bg} p-4`}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-slate-800">{item.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${cfg.border} ${cfg.color}`}>
                  {item.applicability}
                </span>
              </div>
              <div className={`text-sm font-semibold ${cfg.color} mb-1`}>{formatRange(item)}</div>
              <div className="text-xs text-slate-600">{item.basis}</div>
              {item.requiresAdditionalDocs && (
                <div className="mt-1 text-xs text-sky-500">📎 추가자료 제출 후 재산정 가능</div>
              )}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
