import type { ReactNode } from 'react';
import { BookMarked } from 'lucide-react';
import { cn, locationLabel } from '../../utils/format';

export type Tone = 'neutral' | 'brand' | 'success' | 'danger' | 'warning' | 'info';

const tones: Record<Tone, string> = {
  neutral: 'bg-subtle text-body ring-line',
  brand: 'bg-brand-50 text-brand-700 ring-brand-100',
  success: 'bg-success-soft text-success-ink ring-success/20',
  danger: 'bg-danger-soft text-danger-ink ring-danger/20',
  warning: 'bg-warning-soft text-warning-ink ring-warning/25',
  info: 'bg-info-soft text-info-ink ring-info/20',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
  icon,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  icon?: ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        tones[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

/** A page / slide / section citation shown next to source-grounded content. */
export function SourceRef({ type, start, end, className }: { type: string; start: number; end?: number; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded border border-line bg-subtle px-1.5 py-px text-2xs font-medium text-muted',
        className,
      )}
      title="Location in your uploaded document"
    >
      <BookMarked className="h-3 w-3" aria-hidden />
      {locationLabel(type, start, end)}
    </span>
  );
}

export function StatusDot({ tone }: { tone: Tone }) {
  const color = {
    neutral: 'bg-muted',
    brand: 'bg-brand-500',
    success: 'bg-success',
    danger: 'bg-danger',
    warning: 'bg-warning',
    info: 'bg-info',
  }[tone];
  return <span className={cn('inline-block h-2 w-2 rounded-full', color)} aria-hidden />;
}
