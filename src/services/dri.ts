// DRI 서비스: raw 데이터 수집 → signal 점수 변환 → driCalculator 호출
// USE_MOCK=false 시 실제 YouTube/Naver 데이터로 signal 계산

import { calculateDRI } from '../models/driCalculator';
import type { DRIResult, DRISignals } from '../types';
import { mockMonitoringData } from '../data/mockData';

const USE_MOCK = true;

export interface RawSignalData {
  searchTrendPeak: number;       // 0~100 (Naver DataLab 최대값)
  commentVelocityZ: number;      // Z-score (표준화 후 0~100 클리핑)
  toxicityRate: number;          // 0~1
  negativeStanceRate: number;    // 0~1
  duplicateRate: number;         // 0~1
  relatedVideoCount: number;
  totalExposureViews: number;
  newsCount: number;
  snsCount: number;
  blogCount: number;
  suspiciousPatternScore: number; // 0~100
  viewDropRate: number;          // 0~1
  uploadGapDays: number;
}

// raw 데이터 → 각 signal 점수(0~100) 변환
// 나중에 이 함수에 ML 모델 추론 로직을 넣는다
function rawToSignals(raw: RawSignalData): DRISignals {
  const clamp = (v: number) => Math.min(100, Math.max(0, v));

  return {
    searchSpike: clamp(raw.searchTrendPeak),
    commentAttackVelocity: clamp(raw.commentVelocityZ * 6.5), // Z-score → 0~100
    toxicityDuplication: clamp(
      raw.toxicityRate * 50 + raw.negativeStanceRate * 30 + raw.duplicateRate * 20
    ),
    harmfulContentExposure: clamp(
      Math.log10(raw.totalExposureViews + 1) * 12 + raw.relatedVideoCount * 0.4
    ),
    newsSNSAmplification: clamp(
      raw.newsCount * 2 + raw.snsCount * 0.5 + raw.blogCount * 0.3
    ),
    manipulationSignal: clamp(raw.suspiciousPatternScore),
    economicDisruptionSignal: clamp(
      raw.viewDropRate * 60 + Math.min(raw.uploadGapDays * 3, 40)
    ),
  };
}

export async function fetchDRIResult(creatorKeyword: string): Promise<DRIResult> {
  if (USE_MOCK) return mockMonitoringData.dri;

  // 실제 데이터 수집: youtube + naver 서비스 호출 후 signal 계산
  // const videos = await searchRelatedVideos(creatorKeyword);
  // const trend = await fetchSearchTrend(creatorKeyword);
  // const raw = computeRawSignals(videos, trend, ...);
  // const signals = rawToSignals(raw);
  // return calculateDRI(signals);

  throw new Error('실제 DRI 수집 미구현 - USE_MOCK을 false로 변경 후 구현 필요');
}

export { calculateDRI, rawToSignals };
