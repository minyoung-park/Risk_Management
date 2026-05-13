'use client';

import { useState } from 'react';
import type { ExclusionCheckItem } from '../../types';
import SectionCard from '../shared/SectionCard';

interface Props {
  items: ExclusionCheckItem[];
}

export default function ExclusionChecklist({ items }: Props) {
  const [checked, setChecked] = useState<boolean[]>(items.map((i) => i.checked));

  const toggle = (idx: number) =>
    setChecked((prev) => prev.map((v, i) => (i === idx ? !v : v)));

  return (
    <SectionCard title="면책·감액 체크리스트">
      <div className="space-y-3">
        {items.map((item, i) => (
          <label key={i} className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={checked[i]}
              onChange={() => toggle(i)}
              className="sr-only"
            />
            <div
              className={`flex-shrink-0 w-5 h-5 mt-0.5 rounded border-2 flex items-center justify-center transition-colors
                ${checked[i] ? 'bg-red-600 border-red-500' : 'border-slate-300 bg-white'}`}
            >
              {checked[i] && <span className="text-white text-xs">✓</span>}
            </div>
            <div>
              <div className={`text-sm ${checked[i] ? 'text-red-600 font-medium' : 'text-slate-700'}`}>
                {item.label}
              </div>
              {checked[i] && item.note && (
                <div className="text-xs text-slate-500 mt-0.5">{item.note}</div>
              )}
            </div>
          </label>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-600">
        ※ 체크된 항목은 면책 또는 감액 사유에 해당할 수 있습니다. 손해사정사 최종 확인 필요.
      </p>
    </SectionCard>
  );
}
