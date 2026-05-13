'use client';

import { useState } from 'react';
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

type ViewMode = 'subscriber' | 'adjuster';

export default function Dashboard() {
  const { data, loading, error, submitIncident } = useMonitoringData('김재민');
  const [viewMode, setViewMode] = useState<ViewMode>('subscriber');
  const [showModal, setShowModal] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="text-slate-400 text-sm animate-pulse">모니터링 데이터 로딩 중...</div>
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
    <div className="min-h-screen bg-slate-100 text-slate-800">
      {/* 헤더 */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-xs font-bold text-white">
              AI
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-800">AI 안심 케어 보험</div>
              <div className="text-xs text-slate-500">실시간 모니터링 대시보드</div>
            </div>
          </div>

          <div className="flex bg-slate-100 border border-slate-200 rounded-lg p-1 gap-1">
            <TabButton active={viewMode === 'subscriber'} onClick={() => setViewMode('subscriber')}>
              가입자 View
            </TabButton>
            <TabButton active={viewMode === 'adjuster'} onClick={() => setViewMode('adjuster')}>
              손해사정사 View
            </TabButton>
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
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-xl text-sm transition-colors shadow-sm"
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
        ${active ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
    >
      {children}
    </button>
  );
}
