'use client';

import { useState, useEffect } from 'react';
import type { MonitoringData, IncidentInput, IncidentSnapshot } from '../types';
import { mockMonitoringData } from '../data/mockData';
import { fetchDRIResult } from '../services/dri';

const STORAGE_KEY = 'ai_monitoring_snapshots_v1';

function loadStoredSnapshots(): IncidentSnapshot[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
  } catch { return []; }
}

function saveSnapshot(snap: IncidentSnapshot, existing: IncidentSnapshot[]): IncidentSnapshot[] {
  // 같은 시간대(1시간) 중복 저장 방지
  const thisHour = new Date().toISOString().slice(0, 13);
  if (existing[0]?.savedAt.slice(0, 13) === thisHour) return existing;
  const updated = [snap, ...existing].slice(0, 50);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return updated;
}

interface UseMonitoringDataReturn {
  data: MonitoringData | null;
  loading: boolean;
  error: string | null;
  submitIncident: (input: IncidentInput) => void;
}

export function useMonitoringData(creatorKeyword: string): UseMonitoringDataReturn {
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);

        const dri = await fetchDRIResult(creatorKeyword);
        if (cancelled) return;

        // localStorage 스냅샷 로드 (없으면 mock 스냅샷으로 시드)
        let storedSnaps = loadStoredSnapshots();
        if (storedSnaps.length === 0) storedSnaps = mockMonitoringData.snapshots;

        const base: MonitoringData = {
          ...mockMonitoringData,
          dri,
          snapshots: storedSnaps,
          lastUpdated: new Date().toISOString(),
        };

        // DRI >= 75이면 자동 스냅샷 저장
        if (dri.score >= 75) {
          const snap: IncidentSnapshot = {
            savedAt:            new Date().toISOString(),
            driScore:           dri.score,
            driStage:           dri.stage,
            signals:            dri.signals,
            relatedVideos:      mockMonitoringData.snapshots[0]?.relatedVideos ?? 0,
            totalExposureViews: mockMonitoringData.snapshots[0]?.totalExposureViews ?? 0,
            toxicityRate:       mockMonitoringData.snapshots[0]?.toxicityRate ?? 0,
            coverages:          mockMonitoringData.coverages,
            actions:            mockMonitoringData.actions,
            riskUrls:           [],
            evidencePreserved:  false,
          };
          const updated = saveSnapshot(snap, storedSnaps);
          base.snapshots = updated;
        }

        setData(base);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [creatorKeyword]);

  function submitIncident(input: IncidentInput) {
    if (!data) return;
    // 사고 입력 시 스냅샷 즉시 저장
    const snap: IncidentSnapshot = {
      savedAt:            new Date().toISOString(),
      driScore:           data.dri.score,
      driStage:           data.dri.stage,
      signals:            data.dri.signals,
      relatedVideos:      data.snapshots[0]?.relatedVideos ?? 0,
      totalExposureViews: data.snapshots[0]?.totalExposureViews ?? 0,
      toxicityRate:       data.snapshots[0]?.toxicityRate ?? 0,
      coverages:          data.coverages,
      actions:            data.actions,
      riskUrls:           input.problemUrls,
      evidencePreserved:  input.problemUrls.length > 0,
    };
    const updated = saveSnapshot(snap, data.snapshots);
    setData((prev) => prev ? { ...prev, snapshots: updated } : prev);
  }

  return { data, loading, error, submitIncident };
}
