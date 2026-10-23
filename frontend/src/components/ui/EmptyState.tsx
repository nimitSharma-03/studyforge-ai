import type { ReactNode } from 'react';
import { cn } from '../../utils/format';

/** Simple geometric illustration: stacked pages with a highlight, drawn in brand tones. */
export function PagesIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 96" className={className} aria-hidden fill="none">
      <rect x="30" y="14" width="56" height="70" rx="6" fill="rgb(var(--brand-100))" />
      <rect x="22" y="8" width="56" height="70" rx="6" fill="rgb(var(--surface))" stroke="rgb(var(--brand-200))" strokeWidth="1.5" />
      <rect x="31" y="20" width="30" height="4" rx="2" fill="rgb(var(--brand-500))" />
      <rect x="31" y="31" width="38" height="3" rx="1.5" fill="rgb(var(--line-strong))" />
      <rect x="31" y="39" width="34" height="3" rx="1.5" fill="rgb(var(--line-strong))" />
      <rect x="31" y="47" width="36" height="3" rx="1.5" fill="rgb(var(--line-strong))" />
      <rect x="31" y="55" width="22" height="3" rx="1.5" fill="rgb(var(--line-strong))" />
      <circle cx="84" cy="66" r="14" fill="rgb(var(--brand-600))" />
      <path d="m78 66 4 4 8-8" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function EmptyState({
  icon,
  illustration,
  title,
  description,
  action,
  className,
  compact,
}: {
  icon?: ReactNode;
  illustration?: boolean;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center rounded-lg border border-dashed border-line-strong bg-surface text-center',
        compact ? 'px-4 py-8' : 'px-6 py-12',
        className,
      )}
    >
      {illustration ? (
        <PagesIllustration className="mb-4 h-20 w-24" />
      ) : (
        icon && <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-brand-600">{icon}</span>
      )}
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-muted">{description}</p>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
