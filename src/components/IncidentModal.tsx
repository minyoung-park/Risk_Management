'use client';

import { useState } from 'react';
import type { DamageType, CreatorStance, DamageEvidence, IncidentInput } from '../types';

const DAMAGE_TYPES: DamageType[] = ['허위사실 유포', '악성댓글', '사생활 침해', '협박', '사이버렉카 확산', '사칭', '딥페이크'];
const STANCES: CreatorStance[] = ['사실무근', '일부 사실이나 과장됨', '해명 준비 중', '법률 검토 필요'];
const EVIDENCES: DamageEvidence[] = ['광고 취소', '협찬 중단', '후원 감소', '조회수 하락', '업로드 중단', '기타'];

interface Props {
  onSubmit: (input: IncidentInput) => void;
  onClose: () => void;
}

export default function IncidentModal({ onSubmit, onClose }: Props) {
  const [damageTypes, setDamageTypes] = useState<DamageType[]>([]);
  const [stance, setStance] = useState<CreatorStance | ''>('');
  const [evidences, setEvidences] = useState<DamageEvidence[]>([]);
  const [urlInput, setUrlInput] = useState('');
  const [problemUrls, setProblemUrls] = useState<string[]>([]);

  const toggleArr = <T,>(arr: T[], item: T): T[] =>
    arr.includes(item) ? arr.filter((v) => v !== item) : [...arr, item];

  const addUrl = () => {
    const trimmed = urlInput.trim();
    if (trimmed && !problemUrls.includes(trimmed)) {
      setProblemUrls((prev) => [...prev, trimmed]);
      setUrlInput('');
    }
  };

  const handleSubmit = () => {
    if (!stance) return;
    onSubmit({ damageTypes, stance, evidences, problemUrls });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-slate-800 border border-slate-600 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-slate-800 px-6 pt-6 pb-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">사고 정보 입력</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">✕</button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* 피해 유형 */}
          <Section title="1. 피해 유형 (복수 선택)">
            <div className="flex flex-wrap gap-2">
              {DAMAGE_TYPES.map((t) => (
                <ToggleChip
                  key={t} label={t}
                  active={damageTypes.includes(t)}
                  onClick={() => setDamageTypes((p) => toggleArr(p, t))}
                />
              ))}
            </div>
          </Section>

          {/* 본인 입장 */}
          <Section title="2. 본인 입장">
            <div className="space-y-2">
              {STANCES.map((s) => (
                <label key={s} className="flex items-center gap-3 cursor-pointer">
                  <div
                    onClick={() => setStance(s)}
                    className={`w-4 h-4 rounded-full border-2 flex-shrink-0 transition-colors
                      ${stance === s ? 'border-blue-500 bg-blue-500' : 'border-slate-500'}`}
                  />
                  <span className={`text-sm ${stance === s ? 'text-white' : 'text-slate-400'}`}>{s}</span>
                </label>
              ))}
            </div>
          </Section>

          {/* 피해 증빙 */}
          <Section title="3. 피해 증빙 (복수 선택)">
            <div className="flex flex-wrap gap-2">
              {EVIDENCES.map((e) => (
                <ToggleChip
                  key={e} label={e}
                  active={evidences.includes(e)}
                  onClick={() => setEvidences((p) => toggleArr(p, e))}
                />
              ))}
            </div>
          </Section>

          {/* 문제 URL */}
          <Section title="4. 문제 URL">
            <div className="flex gap-2">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addUrl()}
                placeholder="https://..."
                className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={addUrl}
                className="px-3 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600"
              >추가</button>
            </div>
            {problemUrls.length > 0 && (
              <ul className="mt-2 space-y-1">
                {problemUrls.map((url, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 text-xs text-blue-400">
                    <span className="truncate">{url}</span>
                    <button onClick={() => setProblemUrls((p) => p.filter((_, j) => j !== i))} className="text-slate-500 hover:text-red-400 flex-shrink-0">✕</button>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <div className="sticky bottom-0 bg-slate-800 px-6 py-4 border-t border-slate-700 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-lg border border-slate-600 text-slate-400 text-sm hover:bg-slate-700"
          >취소</button>
          <button
            onClick={handleSubmit}
            disabled={!stance}
            className="flex-1 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >제출</button>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-sm font-semibold text-slate-300 mb-2">{title}</div>
      {children}
    </div>
  );
}

function ToggleChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1.5 rounded-full border transition-colors
        ${active ? 'bg-blue-700 border-blue-500 text-white' : 'bg-slate-900 border-slate-600 text-slate-400 hover:border-slate-500'}`}
    >
      {label}
    </button>
  );
}
