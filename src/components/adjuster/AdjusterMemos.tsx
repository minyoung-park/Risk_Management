'use client';

import { useState } from 'react';
import type { AdjusterCoverageNote } from '../../types';
import SectionCard from '../shared/SectionCard';

interface Props {
  notes: AdjusterCoverageNote[];
}

export default function AdjusterMemos({ notes }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <SectionCard title="담보별 심사 메모">
      <div className="space-y-2">
        {notes.map((note) => (
          <div key={note.coverageId} className="border border-slate-700 rounded-lg overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-700/30 transition-colors"
              onClick={() => setOpen(open === note.coverageId ? null : note.coverageId)}
            >
              <span className="text-sm font-medium text-slate-800">{note.coverageName}</span>
              <span className="text-slate-600 text-xs">{open === note.coverageId ? '▲' : '▼'}</span>
            </button>
            {open === note.coverageId && (
              <div className="px-4 pb-4 space-y-2">
                <p className="text-sm text-slate-700">{note.memo}</p>
                {note.requiredDocs.length > 0 && (
                  <div>
                    <div className="text-xs text-slate-600 mb-1">필요 서류</div>
                    <ul className="space-y-1">
                      {note.requiredDocs.map((doc, i) => (
                        <li key={i} className="text-xs text-blue-400 flex gap-1.5">
                          <span>📎</span><span>{doc}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
