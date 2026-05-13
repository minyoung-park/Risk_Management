'use client';

import { useState } from 'react';
import type { DRIResult } from '../types';
import SectionCard from './shared/SectionCard';

const BAR_COLOR = (score: number) => {
  if (score >= 80) return 'bg-rose-500/70';
  if (score >= 60) return 'bg-amber-500/70';
  if (score >= 40) return 'bg-yellow-400/60';
  return 'bg-teal-500/60';
};

const TEXT_COLOR = (score: number) => {
  if (score >= 80) return 'text-rose-300';
  if (score >= 60) return 'text-amber-300';
  if (score >= 40) return 'text-yellow-300';
  return 'text-teal-300';
};

interface Props { dri: DRIResult }

export default function DRIPanel({ dri }: Props) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  return (
    <SectionCard title="DRI 구성요소" badge={`${dri.score}점 · ${dri.stage}`} badgeColor="bg-rose-800/70">
      <div className="space-y-3">
        {dri.signalDetails.map((signal, i) => (
          <div key={signal.label}>
            <button
              className="w-full text-left"
              onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-slate-700">{signal.label}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">가중치 {(signal.weight * 100).toFixed(0)}%</span>
                  <span className={`text-sm font-semibold ${TEXT_COLOR(signal.score)}`}>{signal.score}</span>
                  <span className="text-slate-500 text-xs">{expandedIndex === i ? '▲' : '▼'}</span>
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all duration-500 ${BAR_COLOR(signal.score)}`}
                  style={{ width: `${signal.score}%` }}
                />
              </div>
            </button>

            {expandedIndex === i && (
              <div className="mt-2 ml-1 bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs text-slate-600 space-y-2">
                <p className="text-slate-700">{signal.description}</p>
                <ul className="space-y-1">
                  {signal.subFactors.map((f, j) => (
                    <li key={j} className="flex items-start gap-1.5">
                      <span className="text-slate-400 mt-0.5">·</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <p className="text-slate-500">
                  기여 점수: {signal.score} × {(signal.weight * 100).toFixed(0)}% = {(signal.score * signal.weight).toFixed(1)}점
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-5 gap-1 text-center text-xs">
        {[
          { range: '0~39',   stage: 'Normal',  color: 'text-teal-500' },
          { range: '40~59',  stage: 'Watch',   color: 'text-amber-500' },
          { range: '60~74',  stage: 'Alert',   color: 'text-orange-500' },
          { range: '75~89',  stage: 'Trigger', color: 'text-rose-500' },
          { range: '90~100', stage: 'Severe',  color: 'text-rose-700' },
        ].map(({ range, stage, color }) => (
          <div key={stage} className={`${stage === dri.stage ? 'bg-slate-100 rounded' : ''} py-1`}>
            <div className={`font-semibold ${color}`}>{stage}</div>
            <div className="text-slate-500">{range}</div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
