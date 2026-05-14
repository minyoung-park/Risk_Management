// DRI 서비스: raw 데이터 수집 → signal 점수 변환 → driCalculator 호출
// USE_MOCK=false 시 실제 YouTube/Naver 데이터로 signal 계산

import { calculateDRI } from '../models/driCalculator';
import type { DRIResult, DRISignals } from '../types';
import { mockMonitoringData } from '../data/mockData';
import { USE_MOCK } from '../config';

export interface RawSignalData {
  searchTrendPeak: number;        // 0~100 fallback
  commentVelocityZ: number;       // Z-score
  toxicityRate: number;           // 0~1 (욕설/혐오 = 독성키워드)
  negativeStanceRate: number;     // 0~1 (실망/비난 = 부정감성)
  duplicateRate: number;          // 0~1
  relatedVideoCount: number;
  totalExposureViews: number;
  newsCount: number;
  snsCount: number;
  blogCount: number;
  suspiciousPatternScore: number; // 0~100
  viewDropRate: number;           // 0~1
  uploadGapDays: number;
  // 노트북 방식으로 사전 계산된 점수 (있으면 우선 사용)
  searchSpikeScore?: number;      // 1년치 Z-score 기반 0~100
  hceScore?: number;              // 제3자뷰/본인평균뷰 × 10 기반 0~100
  newsSNSScore?: number;          // 일별 기사량 Z-score × 20 기반 0~100
  toxicityScore?: number;         // 영상제목·자막 기반 neg×0.5+title_toxic×0.3+script_toxic×0.2
}

function rawToSignals(raw: RawSignalData): DRISignals {
  const clamp = (v: number) => Math.min(100, Math.max(0, v));

  return {
    searchSpike: clamp(raw.searchSpikeScore ?? raw.searchTrendPeak),
    commentAttackVelocity: clamp(raw.commentVelocityZ * 6.5),
    // 노트북: neg×0.5 + title_toxic×0.3 + script_toxic×0.2 (영상 기반 사전계산 우선)
    toxicityDuplication: clamp(
      raw.toxicityScore ??
      (raw.negativeStanceRate * 50 + raw.toxicityRate * 30 + raw.duplicateRate * 20)
    ),
    // 노트북: (제3자총뷰 / 본인채널평균뷰) × 10
    harmfulContentExposure: clamp(
      raw.hceScore ??
      (Math.max(0, Math.log10(raw.totalExposureViews + 1) - 5) * 20 + raw.relatedVideoCount * 0.5)
    ),
    // 노트북: 일별 기사 Z-score × 20
    newsSNSAmplification: clamp(
      raw.newsSNSScore ??
      (raw.newsCount * 0.7 + raw.snsCount * 0.5 + raw.blogCount * 0.3)
    ),
    manipulationSignal: clamp(raw.suspiciousPatternScore),
    economicDisruptionSignal: clamp(
      raw.viewDropRate * 60 + Math.min(raw.uploadGapDays * 3, 40)
    ),
  };
}

export async function fetchDRIResult(creatorKeyword: string, analysisDate?: string, creatorName?: string): Promise<DRIResult> {
  if (USE_MOCK) return mockMonitoringData.dri;

  const params = new URLSearchParams({ keyword: creatorKeyword });
  if (analysisDate) params.set('date', analysisDate);
  if (creatorName) params.set('name', creatorName);
  const res = await fetch(`/api/dri?${params.toString()}`);
  if (!res.ok) throw new Error(`DRI API 오류: ${res.status}`);
  return res.json();
}

export { calculateDRI, rawToSignals };
