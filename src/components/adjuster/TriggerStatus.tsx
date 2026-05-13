'use client';

import type { AdjusterData } from '../../types';
import SectionCard from '../shared/SectionCard';

interface Props {
  adjuster: AdjusterData;
  driScore: number;
}

export default function TriggerStatus({ adjuster, driScore }: Props) {
  return (
    <SectionCard
      title="트리거 충족 여부"
      badge={adjuster.triggerMet ? '충족' : '미충족'}
      badgeColor={adjuster.triggerMet ? 'bg-rose-900/60' : 'bg-gray-700/60'}
    >
      <div className={`rounded-lg p-4 border ${adjuster.triggerMet ? 'bg-rose-50 border-rose-200' : 'bg-slate-50 border-slate-200'}`}>
        <div className={`text-sm font-medium mb-1 ${adjuster.triggerMet ? 'text-rose-600' : 'text-slate-400'}`}>
          {adjuster.triggerMet ? '✓ 트리거 기준 충족' : '✗ 트리거 기준 미충족'}
        </div>
        <div className="text-sm text-slate-600">{adjuster.triggerBasis}</div>
        <div className="mt-2 text-xs text-slate-400">현재 DRI: {driScore}점 / 기준: 75점</div>
      </div>
    </SectionCard>
  );
}
