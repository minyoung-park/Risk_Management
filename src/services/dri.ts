// DRI 서비스: raw 데이터 수집 → signal 점수 변환 → driCalculator 호출
// USE_MOCK=false 시 실제 YouTube/Naver 데이터로 signal 계산

import { calculateDRI } from '../models/driCalculator';
import type { DRIResult, DRISignals } from '../types';
import { mockMonitoringData } from '../data/mockData';
import { USE_MOCK } from '../config';

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
    // 최근 7일 vs 이전 23일 급등 비율 기반 (2배 급등 = 100점)
    searchSpike: clamp(raw.searchTrendPeak),
    commentAttackVelocity: clamp(raw.commentVelocityZ * 6.5),
    toxicityDuplication: clamp(
      raw.toxicityRate * 50 + raw.negativeStanceRate * 30 + raw.duplicateRate * 20
    ),
    // 제3자 영상만 집계: 1M뷰=20점, 10M=40점, 100M=60점, 1B=80점
    harmfulContentExposure: clamp(
      Math.max(0, Math.log10(raw.totalExposureViews + 1) - 5) * 20
      + raw.relatedVideoCount * 0.5
    ),
    // newsCount/blogCount = 최근 30일 실수 (0~100): 100건=70점 기준
    newsSNSAmplification: clamp(
      raw.newsCount * 0.7 + raw.snsCount * 0.5 + raw.blogCount * 0.3
    ),
    manipulationSignal: clamp(raw.suspiciousPatternScore),
    economicDisruptionSignal: clamp(
      raw.viewDropRate * 60 + Math.min(raw.uploadGapDays * 3, 40)
    ),
  };
}

export async function fetchDRIResult(creatorKeyword: string): Promise<DRIResult> {
  if (USE_MOCK) return mockMonitoringData.dri;

  const res = await fetch(`/api/dri?keyword=${encodeURIComponent(creatorKeyword)}`);
  if (!res.ok) throw new Error(`DRI API 오류: ${res.status}`);
  return res.json();
}

export { calculateDRI, rawToSignals };
