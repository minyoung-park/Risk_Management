'use client';

import type { AdjusterData } from '../../types';
import SectionCard from '../shared/SectionCard';

interface Props {
  docs: AdjusterData['requiredDocs'];
}

export default function RequiredDocs({ docs }: Props) {
  return (
    <SectionCard title="필요 추가자료">
      <ul className="space-y-2">
        {docs.map((doc, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className="text-blue-400 flex-shrink-0">📎</span>
            <span className="text-slate-700">{doc}</span>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
