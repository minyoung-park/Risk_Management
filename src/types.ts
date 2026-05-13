// ─── DRI ──────────────────────────────────────────────────────────────────────

export type DRIStage = 'Normal' | 'Watch' | 'Alert' | 'Trigger' | 'Severe';

export interface DRISignals {
  searchSpike: number;           // 0~100
  commentAttackVelocity: number; // 0~100
  toxicityDuplication: number;   // 0~100
  harmfulContentExposure: number;// 0~100
  newsSNSAmplification: number;  // 0~100
  manipulationSignal: number;    // 0~100
  economicDisruptionSignal: number; // 0~100
}

export interface DRISignalDetail {
  label: string;
  score: number;
  weight: number;
  description: string;
  subFactors: string[];
}

export interface DRIResult {
  score: number;
  stage: DRIStage;
  signals: DRISignals;
  signalDetails: DRISignalDetail[];
}

// ─── 크리에이터 프로필 ───────────────────────────────────────────────────────────

export interface CreatorProfile {
  name: string;
  channelName: string;
  subscribers: number;
  avgViews: number;
  hasMCN: boolean;
  hasLawyer: boolean;
  hasPRManager: boolean;
  youtubeAnalyticsConsent: boolean;
  activeContracts: number;
  contractCancelled: boolean;
  platformDependency: 'YouTube' | 'Multi' | 'Twitch';
}

// ─── 담보 ────────────────────────────────────────────────────────────────────

export type CoverageApplicability = '높음' | '중간' | '낮음' | '보류';

export interface CoverageItem {
  id: string;
  name: string;
  applicability: CoverageApplicability;
  rangeMin: number | null; // null = 산정 제외
  rangeMax: number | null;
  basis: string;
  requiresAdditionalDocs: boolean;
}

// ─── 권장 조치 ───────────────────────────────────────────────────────────────

export interface RecommendedAction {
  order: number;
  text: string;
  priority: 'urgent' | 'normal';
}

// ─── 사고 스냅샷 ─────────────────────────────────────────────────────────────

export interface IncidentSnapshot {
  savedAt: string;
  driScore: number;
  driStage: DRIStage;
  signals: DRISignals;
  relatedVideos: number;
  totalExposureViews: number;
  toxicityRate: number;
  coverages: CoverageItem[];
  actions: RecommendedAction[];
  riskUrls: string[];
  evidencePreserved: boolean;
}

// ─── 사고 입력 (모달) ────────────────────────────────────────────────────────

export type DamageType =
  | '허위사실 유포'
  | '악성댓글'
  | '사생활 침해'
  | '협박'
  | '사이버렉카 확산'
  | '사칭'
  | '딥페이크';

export type CreatorStance =
  | '사실무근'
  | '일부 사실이나 과장됨'
  | '해명 준비 중'
  | '법률 검토 필요';

export type DamageEvidence =
  | '광고 취소'
  | '협찬 중단'
  | '후원 감소'
  | '조회수 하락'
  | '업로드 중단'
  | '기타';

export interface IncidentInput {
  damageTypes: DamageType[];
  stance: CreatorStance;
  evidences: DamageEvidence[];
  problemUrls: string[];
}

// ─── 손해사정사 전용 ─────────────────────────────────────────────────────────

export interface AdjusterCoverageNote {
  coverageId: string;
  coverageName: string;
  memo: string;
  requiredDocs: string[];
}

export interface ExclusionCheckItem {
  label: string;
  checked: boolean;
  note?: string;
}

export interface DataReliabilityItem {
  source: string;
  reliability: 'high' | 'medium' | 'low';
  reason: string;
}

export interface AdjusterData {
  triggerMet: boolean;
  triggerBasis: string;
  coverageNotes: AdjusterCoverageNote[];
  requiredDocs: string[];
  exclusionChecklist: ExclusionCheckItem[];
  dataReliability: DataReliabilityItem[];
}

// ─── 관련 영상 목록 ──────────────────────────────────────────────────────────

export interface RelatedVideo {
  videoId: string;
  title: string;
  channelName: string;
  publishedAt: string;
  viewCount: number;
  url: string;
  isCyberjacker: boolean; // 사이버렉카 여부
}

// ─── 평시 모니터링 ────────────────────────────────────────────────────────────

export type MonitorStatus = 'active' | 'warning' | 'idle';

export interface MonitorChannel {
  label: string;
  status: MonitorStatus;
  count: number;       // 감지된 건수
  lastChecked: string; // ISO
}

export interface DRITrendPoint {
  date: string;  // 'MM.DD'
  score: number;
}

export interface EvidenceVaultSummary {
  savedUrls: number;
  autoSnapshots: number;
  lastSavedAt: string;
}

export interface ReadinessItem {
  label: string;
  done: boolean;
  action?: string; // 미완료 시 안내 문구
}

export interface ProactiveMonitoringData {
  channels: MonitorChannel[];
  driTrend: DRITrendPoint[];
  evidenceVault: EvidenceVaultSummary;
  readiness: ReadinessItem[];
}

// ─── 전체 모니터링 데이터 ────────────────────────────────────────────────────

export interface MonitoringData {
  creator: CreatorProfile;
  dri: DRIResult;
  coverages: CoverageItem[];
  actions: RecommendedAction[];
  snapshots: IncidentSnapshot[];   // 히스토리 (최신순)
  adjuster: AdjusterData;
  relatedVideos: RelatedVideo[];
  proactive: ProactiveMonitoringData;
  lastUpdated: string;
}
