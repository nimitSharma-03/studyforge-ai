import { cn } from '../utils/format';

/** StudyForge mark: an open notebook whose right page carries a check — notes becoming verified knowledge. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('h-8 w-8', className)} aria-hidden fill="none">
      <rect width="32" height="32" rx="8" fill="rgb(var(--navy))" />
      <path d="M9 10.5c0-.83.67-1.5 1.5-1.5H16v14h-5.5A1.5 1.5 0 0 1 9 21.5v-11Z" fill="rgb(var(--brand-300))" />
      <path d="M16 9h5.5c.83 0 1.5.67 1.5 1.5v11c0 .83-.67 1.5-1.5 1.5H16V9Z" fill="rgb(var(--brand-500))" />
      <path d="M12 13h2.5M12 16h2.5M18 13h2.5M18 16h2.5" stroke="rgb(var(--navy))" strokeWidth="1.4" strokeLinecap="round" />
      <path d="m18.2 19.2 1.2 1.2 2.2-2.4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      {!compact && (
        <span className="text-[17px] font-semibold tracking-tight text-ink">
          StudyForge <span className="text-brand-600">AI</span>
        </span>
      )}
    </span>
  );
}
