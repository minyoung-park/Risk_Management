'use client';

interface SectionCardProps {
  title: string;
  badge?: string;
  badgeColor?: string;
  children: React.ReactNode;
  className?: string;
}

export default function SectionCard({ title, badge, badgeColor = 'bg-slate-700', children, className = '' }: SectionCardProps) {
  return (
    <div className={`bg-white border border-slate-200 rounded-xl p-5 shadow-sm ${className}`}>
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wider">{title}</h2>
        {badge && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badgeColor} text-white`}>
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}
