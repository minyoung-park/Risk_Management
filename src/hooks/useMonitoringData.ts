'use client';

import { useState, useEffect } from 'react';
import type { MonitoringData, IncidentInput } from '../types';
import { mockMonitoringData } from '../data/mockData';
import { fetchDRIResult } from '../services/dri';
import { generateSummary } from '../services/llm';

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

        setData({
          ...mockMonitoringData,
          dri,
          lastUpdated: new Date().toISOString(),
          relatedVideos: mockMonitoringData.relatedVideos,
          proactive: mockMonitoringData.proactive,
        });
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
    setData((prev) => prev ? { ...prev } : prev);
  }

  return { data, loading, error, submitIncident };
}
