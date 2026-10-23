import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, ServerCrash, XCircle } from 'lucide-react';
import type { ApiError } from '../../services/api';
import { cn } from '../../utils/format';
import { Button } from './Button';

type AlertTone = 'info' | 'success' | 'warning' | 'danger';

const alertStyles: Record<AlertTone, { box: string; icon: ReactNode }> = {
  info: { box: 'border-info/20 bg-info-soft text-info-ink', icon: <Info className="h-4 w-4" /> },
  success: { box: 'border-success/20 bg-success-soft text-success-ink', icon: <CheckCircle2 className="h-4 w-4" /> },
  warning: { box: 'border-warning/25 bg-warning-soft text-warning-ink', icon: <AlertTriangle className="h-4 w-4" /> },
  danger: { box: 'border-danger/20 bg-danger-soft text-danger-ink', icon: <XCircle className="h-4 w-4" /> },
};

export function Alert({
  tone = 'info',
  title,
  children,
  action,
  className,
}: {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const style = alertStyles[tone];
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className={cn('flex gap-3 rounded-md border px-4 py-3 text-sm', style.box, className)}>
      <span className="mt-0.5 shrink-0">{style.icon}</span>
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title ? 'mt-0.5' : undefined, 'opacity-90')}>{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  );
}

export function Spinner({ label = 'Loading', className }: { label?: string; className?: string }) {
  return (
    <span role="status" className={cn('inline-flex items-center gap-2 text-sm text-muted', className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-subtle', className)} aria-hidden />;
}

export function PageLoader({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="space-y-4" aria-busy="true">
      <Spinner label={label} />
      <Skeleton className="h-24 w-full" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    </div>
  );
}

export function ProgressBar({
  value,
  tone = 'brand',
  className,
  label,
}: {
  value: number;
  tone?: 'brand' | 'success' | 'warning' | 'danger';
  className?: string;
  label?: string;
}) {
  const color = { brand: 'bg-brand-600', success: 'bg-success', warning: 'bg-warning', danger: 'bg-danger' }[tone];
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      className={cn('h-2 w-full overflow-hidden rounded-full bg-subtle', className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped * 100)}
      aria-label={label}
    >
      <div className={cn('h-full rounded-full transition-[width] duration-300', color)} style={{ width: `${clamped * 100}%` }} />
    </div>
  );
}

export function IndeterminateBar({ className }: { className?: string }) {
  return (
    <div className={cn('relative h-1.5 w-full overflow-hidden rounded-full bg-brand-100', className)} aria-hidden>
      <div className="absolute inset-y-0 w-1/3 animate-indeterminate rounded-full bg-brand-600" />
    </div>
  );
}

/** Error panel for failed page loads; distinguishes an unreachable backend from other errors. */
export function ErrorState({ error, onRetry, className }: { error: ApiError; onRetry?: () => void; className?: string }) {
  const offline = error.isNetwork || error.code === 'server_unavailable';
  const database = error.code === 'database_unavailable' || error.code === 'database_error';
  const title = offline ? 'Server unavailable' : database ? 'Database unavailable' : 'Something went wrong';
  return (
    <div className={cn('flex flex-col items-center rounded-lg border border-line bg-surface px-6 py-10 text-center', className)}>
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-danger-soft text-danger">
        <ServerCrash className="h-5 w-5" aria-hidden />
      </span>
      <h2 className="mt-4 text-base font-semibold">{title}</h2>
      <p className="mt-1 max-w-md text-sm text-muted">{error.message}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-5" onClick={onRetry} icon={<RefreshCw className="h-4 w-4" />}>
          Try again
        </Button>
      )}
    </div>
  );
}
