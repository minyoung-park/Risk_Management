'use client';

import type { RecommendedAction } from '../types';
import SectionCard from './shared/SectionCard';

interface Props {
  actions: RecommendedAction[];
  stage: string;
}

export default function RecommendedActions({ actions, stage }: Props) {
  return (
    <SectionCard title="권장 조치" badge={stage} badgeColor="bg-amber-500">
      <ol className="space-y-2.5">
        {actions.map((action) => (
          <li key={action.order} className="flex items-start gap-3">
            <span
              className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-semibold
                ${action.priority === 'urgent'
                  ? 'bg-rose-100 text-rose-600 border border-rose-200'
                  : 'bg-slate-100 text-slate-400 border border-slate-200'}`}
            >
              {action.order}
            </span>
            <span className={`text-sm pt-0.5 leading-relaxed ${action.priority === 'urgent' ? 'text-slate-700' : 'text-slate-600'}`}>
              {action.text}
              {action.priority === 'urgent' && (
                <span className="ml-2 text-xs text-rose-400/80">긴급</span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </SectionCard>
  );
}
