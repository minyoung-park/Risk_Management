'use client';

import { useState } from 'react';
import Image from 'next/image';
import { useMonitoringData } from '../hooks/useMonitoringData';
import KPISummary from './KPISummary';
import DRIPanel from './DRIPanel';
import CoveragePanel from './CoveragePanel';
import RecommendedActions from './RecommendedActions';
import CreatorProfileCard from './CreatorProfileCard';
import SnapshotHistory from './SnapshotHistory';
import SecurityPrinciples from './SecurityPrinciples';
import IncidentModal from './IncidentModal';
import TriggerStatus from './adjuster/TriggerStatus';
import AdjusterMemos from './adjuster/AdjusterMemos';
import RequiredDocs from './adjuster/RequiredDocs';
import ExclusionChecklist from './adjuster/ExclusionChecklist';
import DataReliability from './adjuster/DataReliability';
import RelatedVideosList from './RelatedVideosList';
import ProactiveMonitoring from './ProactiveMonitoring';
import DRITrendChart from './DRITrendChart';

type ViewMode = 'subscriber' | 'adjuster';

// YouTube URL / @handle / 채널ID / 채널명 → API로 넘길 키워드 추출
function extractKeyword(input: string): string {
  const trimmed = input.trim();
  // youtube.com/channel/UCxxx → 채널 ID 직접 추출
  const channelIdMatch = trimmed.match(/youtube\.com\/channel\/(UC[\w-]+)/i);
  if (channelIdMatch) return channelIdMatch[1];
  // youtube.com/@handle → @handle 형식으로
  const urlHandleMatch = trimmed.match(/youtube\.com\/@([\w.-]+)/i);
  if (urlHandleMatch) return `@${urlHandleMatch[1]}`;
  // youtube.com/c/name 또는 /user/name → 이름만 추출
  const legacyMatch = trimmed.match(/youtube\.com\/(?:c|user)\/([\w.-]+)/i);
  if (legacyMatch) return legacyMatch[1];
  // @handle 직접 입력 → 그대로
  if (trimmed.startsWith('@')) return trimmed;
  // 나머지 → 키워드 그대로
  return trimmed;
}

export default function Dashboard() {
  const todayStr = new Date().toISOString().slice(0, 10);

  const [inputValue, setInputValue]     = useState('워크맨');
  const [nameValue, setNameValue]       = useState('');
  const [keyword, setKeyword]           = useState('워크맨');
  const [creatorName, setCreatorName]   = useState('');
  const [analysisDate, setAnalysisDate] = useState(todayStr);
  const { data, loading, error, submitIncident } = useMonitoringData(keyword, analysisDate, creatorName);
  const [viewMode, setViewMode]       = useState<ViewMode>('subscriber');
  const [showModal, setShowModal]     = useState(false);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const kw = extractKeyword(inputValue);
    if (kw) setKeyword(kw);
    setCreatorName(nameValue.trim());
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-slate-400 text-sm animate-pulse">
          &quot;{keyword}&quot; 분석 중...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-rose-500 text-sm">데이터 로드 실패: {error}</div>
      </div>
    );
  }

  const { creator, dri, coverages, actions, snapshots, adjuster, relatedVideos, proactive, lastUpdated } = data;
  const latestSnap = snapshots[0];
  const totalViews = latestSnap?.totalExposureViews ?? relatedVideos.reduce((sum, v) => sum + v.viewCount, 0);
  const relatedVideoCount = latestSnap?.relatedVideos ?? relatedVideos.length;

  return (
    <div className="min-h-screen bg-[#f0f4f8] text-slate-800">
      {/* 헤더 */}
      <header className="bg-white sticky top-0 z-40 shadow-sm border-b-2 border-[#0038A8]">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#0038A8] rounded-lg flex items-center justify-center text-xs font-bold text-white">
              AI
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-800">AI 안심 케어 보험</div>
              <div className="text-xs text-slate-500">실시간 모니터링 대시보드</div>
            </div>
            <div className="relative h-7 w-24 flex-shrink-0">
              <Image src="/sf-logo.png" alt="삼성화재" fill className="object-contain object-left" />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <form onSubmit={handleSearch} className="flex items-center gap-1">
              <input
                type="text"
                value={nameValue}
                onChange={e => setNameValue(e.target.value)}
                placeholder="한글 이름 (예: 쯔양)"
                className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 w-28 focus:outline-none focus:border-[#0038A8]"
              />
              <input
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                placeholder="채널 URL 또는 @핸들"
                className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 w-48 focus:outline-none focus:border-[#0038A8]"
              />
              <input
                type="date"
                value={analysisDate}
                max={todayStr}
                onChange={e => { if (e.target.value) setAnalysisDate(e.target.value); }}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-[#0038A8]"
              />
              <button
                type="submit"
                className="text-xs bg-[#0038A8] hover:bg-[#002d87] text-white px-3 py-1.5 rounded-lg"
              >
                분석
              </button>
            </form>

            <div className="flex bg-slate-100 border border-slate-200 rounded-lg p-1 gap-1">
              <TabButton active={viewMode === 'subscriber'} onClick={() => setViewMode('subscriber')}>
                가입자 View
              </TabButton>
              <TabButton active={viewMode === 'adjuster'} onClick={() => setViewMode('adjuster')}>
                손해사정사 View
              </TabButton>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-5">
        <KPISummary
          dri={dri}
          relatedVideos={relatedVideoCount}
          totalExposureViews={totalViews}
          lastUpdated={lastUpdated}
        />

        {dri.trendSeries && dri.trendSeries.length > 0 && (
          <DRITrendChart trendSeries={dri.trendSeries} refDate={analysisDate} />
        )}

        {viewMode === 'adjuster' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <TriggerStatus adjuster={adjuster} driScore={dri.score} />
            <RequiredDocs docs={adjuster.requiredDocs} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <DRIPanel dri={dri} />
            <RelatedVideosList videos={relatedVideos} totalCount={relatedVideoCount} />
            <CoveragePanel coverages={coverages} />
            {viewMode === 'adjuster' && (
              <AdjusterMemos notes={adjuster.coverageNotes} />
            )}
            <SnapshotHistory snapshots={snapshots} />
          </div>

          <div className="space-y-4">
            <RecommendedActions actions={actions} stage={dri.stage} />
            <CreatorProfileCard creator={creator} />

            <button
              onClick={() => setShowModal(true)}
              className="w-full py-3 bg-[#0038A8] hover:bg-[#002d87] text-white font-medium rounded-xl text-sm transition-colors shadow-sm"
            >
              + 사고 정보 입력
            </button>

            <ProactiveMonitoring data={proactive} />

            <SecurityPrinciples />

            {viewMode === 'adjuster' && (
              <>
                <ExclusionChecklist items={adjuster.exclusionChecklist} />
                <DataReliability items={adjuster.dataReliability} />
              </>
            )}
          </div>
        </div>
      </main>

      {showModal && (
        <IncidentModal onSubmit={submitIncident} onClose={() => setShowModal(false)} />
      )}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors
        ${active ? 'bg-white text-[#0038A8] shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
    >
      {children}
    </button>
  );
}
