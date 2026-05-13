'use client';

import type { CreatorProfile } from '../types';
import SectionCard from './shared/SectionCard';

function Badge({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium
      ${active
        ? 'bg-teal-50 border-teal-200 text-teal-600'
        : 'bg-slate-50 border-slate-200 text-slate-500'}`}>
      {active ? '✓' : '✗'} {label}
    </span>
  );
}

interface Props { creator: CreatorProfile }

export default function CreatorProfileCard({ creator }: Props) {
  return (
    <SectionCard title="가입자 프로필">
      <div className="space-y-4">
        <div>
          <div className="text-base font-semibold text-slate-800">{creator.name}</div>
          <div className="text-slate-500 text-sm">{creator.channelName}</div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <Stat label="구독자" value={formatNum(creator.subscribers)} />
          <Stat label="평균 조회수" value={formatNum(creator.avgViews)} />
          <Stat label="플랫폼" value={creator.platformDependency} />
          <Stat label="진행 계약" value={`${creator.activeContracts}건${creator.contractCancelled ? ' (취소)' : ''}`} />
        </div>

        <div>
          <div className="text-xs text-slate-500 mb-2">대응 체계</div>
          <div className="flex flex-wrap gap-2">
            <Badge label="MCN" active={creator.hasMCN} />
            <Badge label="변호사" active={creator.hasLawyer} />
            <Badge label="PR 담당자" active={creator.hasPRManager} />
          </div>
        </div>

        <div>
          <div className="text-xs text-slate-500 mb-2">데이터 연동</div>
          <Badge label="YouTube Analytics" active={creator.youtubeAnalyticsConsent} />
          {!creator.youtubeAnalyticsConsent && (
            <p className="text-xs text-amber-600 mt-1.5">⚠ Analytics 미연동 — 수익중단손해 신뢰도 낮음</p>
          )}
        </div>
      </div>
    </SectionCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-slate-800 font-medium">{value}</div>
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 10_000) return `${(n / 10_000).toFixed(0)}만`;
  return n.toLocaleString();
}
