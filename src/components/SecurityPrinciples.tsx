'use client';

import SectionCard from './shared/SectionCard';

const PRINCIPLES = [
  { icon: '🔒', title: 'Raw Data Storage', desc: '원본 댓글·URL·계약서는 암호화 저장, 접근권한 제한' },
  { icon: '🎭', title: 'Anonymization Layer', desc: '이름·계좌·광고주명 마스킹, 댓글 작성자 ID 해시 처리' },
  { icon: '🤖', title: 'AI Analysis Layer', desc: '비식별화된 지표와 샘플만 LLM 입력 — 원본 문서·API 토큰 입력 금지' },
  { icon: '🗄️', title: 'Evidence Vault', desc: '원본 증거 별도 보관, 해시값·타임스탬프·감사 로그 저장' },
  { icon: '👤', title: 'Human Review', desc: '고위험 사건은 손해사정사 또는 법률전문가 최종 확인' },
];

export default function SecurityPrinciples() {
  return (
    <SectionCard title="AI 보안 처리 원칙">
      <div className="space-y-3">
        {PRINCIPLES.map((p) => (
          <div key={p.title} className="flex gap-3 items-start">
            <span className="text-lg flex-shrink-0">{p.icon}</span>
            <div>
              <div className="text-sm font-semibold text-slate-700">{p.title}</div>
              <div className="text-xs text-slate-500 mt-0.5">{p.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
