'use client';

import { useMemo } from 'react';
import type { TrendDataPoint } from '../types';

interface Props {
  trendSeries: TrendDataPoint[];
  refDate?: string; // YYYY-MM-DD — 분석 기준일 (마커 표시)
}

export default function DRITrendChart({ trendSeries, refDate }: Props) {
  const chart = useMemo(() => {
    const n = trendSeries.length;
    if (n < 2) return null;

    const W = 380, H = 70, ox = 10, oy = 5;
    const maxRatio = Math.max(
      ...trendSeries.map(p => Math.max(p.baseRatio, p.controversyRatio)),
      1,
    );

    const toX = (i: number) => ox + (i / (n - 1)) * W;
    const toY = (v: number) => oy + H - (v / maxRatio) * H;

    const basePath = trendSeries
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.baseRatio).toFixed(1)}`)
      .join(' ');
    const controversyPath = trendSeries
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.controversyRatio).toFixed(1)}`)
      .join(' ');

    // mean ± 1σ for base trend (평상시 변동폭)
    const baseVals = trendSeries.map(p => p.baseRatio);
    const m = baseVals.reduce((a, b) => a + b, 0) / n;
    const s = Math.sqrt(baseVals.reduce((a, b) => a + Math.pow(b - m, 2), 0) / n);

    const meanY    = toY(m);
    const bandTopY = toY(Math.min(m + s, maxRatio));
    const bandBotY = toY(Math.max(m - s, 0));

    // 기준일 위치: refDate와 일치하는 포인트 또는 마지막 7일 경계
    let refX: number | null = null;
    if (refDate) {
      const idx = trendSeries.findIndex(p => p.date >= refDate);
      if (idx >= 0) refX = toX(idx);
    }
    if (refX === null && n >= 7) refX = toX(n - 7);

    return {
      basePath,
      controversyPath,
      meanY,
      bandTopY,
      bandBotY,
      refX,
      meanLabel: Math.round(m * 10) / 10,
      stdLabel:  Math.round(s * 10) / 10,
    };
  }, [trendSeries, refDate]);

  if (!chart) return null;

  const firstDate = trendSeries[0]?.date.slice(5) ?? '';
  const lastDate  = trendSeries[trendSeries.length - 1]?.date.slice(5) ?? '';

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-semibold text-slate-700">검색 트렌드 (30일)</div>
        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-5 h-px bg-blue-500" />
            기본 검색
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-5 h-px bg-rose-400" />
            논란 검색
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-2.5 bg-slate-200 opacity-80 rounded-sm" />
            평시 변동폭
          </span>
        </div>
      </div>

      <svg
        viewBox="0 0 400 80"
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
        style={{ overflow: 'visible' }}
      >
        {/* 평상시 변동폭 밴드 (mean ± 1σ) */}
        <rect
          x="10"
          y={chart.bandTopY}
          width="380"
          height={chart.bandBotY - chart.bandTopY}
          fill="#cbd5e1"
          fillOpacity="0.4"
        />
        {/* 평균선 */}
        <line
          x1="10" x2="390"
          y1={chart.meanY} y2={chart.meanY}
          stroke="#94a3b8" strokeWidth="0.8" strokeDasharray="4,3"
        />
        {/* 기준일 이전 7일 하이라이트 */}
        {chart.refX !== null && (
          <>
            <rect
              x={chart.refX} y="5"
              width={390 - chart.refX} height="70"
              fill="#fef3c7" fillOpacity="0.35"
            />
            <line
              x1={chart.refX} x2={chart.refX}
              y1="5" y2="75"
              stroke="#f59e0b" strokeWidth="1" strokeDasharray="3,2" opacity="0.8"
            />
          </>
        )}
        {/* 기본 키워드 트렌드 */}
        <path
          d={chart.basePath}
          fill="none" stroke="#3b82f6" strokeWidth="1.5" strokeLinejoin="round"
        />
        {/* 논란 키워드 트렌드 */}
        <path
          d={chart.controversyPath}
          fill="none" stroke="#f43f5e" strokeWidth="1.5" strokeLinejoin="round"
        />
      </svg>

      <div className="flex justify-between text-[10px] text-slate-400 mt-1">
        <span>{firstDate}</span>
        <span>평시 평균 {chart.meanLabel} · 변동폭 ±{chart.stdLabel}</span>
        <span>{lastDate}</span>
      </div>
    </div>
  );
}
