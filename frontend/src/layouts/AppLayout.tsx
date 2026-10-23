import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  BarChart3,
  BookOpenText,
  ClipboardCheck,
  FolderOpen,
  Info,
  LayoutDashboard,
  ListChecks,
  Menu,
  Upload,
  X,
} from 'lucide-react';
import { Logo } from '../components/Logo';
import { Alert } from '../components/ui/Feedback';
import { Button } from '../components/ui/Button';
import { useServer } from '../hooks/useServer';
import { cn } from '../utils/format';

const NAV = [
  { to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/materials', label: 'My Materials', icon: FolderOpen },
  { to: '/app/upload', label: 'Upload', icon: Upload },
  { to: '/app/learn', label: 'Learn', icon: BookOpenText },
  { to: '/app/questions', label: 'Question Bank', icon: ListChecks },
  { to: '/app/practice', label: 'Practice Tests', icon: ClipboardCheck },
  { to: '/app/progress', label: 'Progress', icon: BarChart3 },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive ? 'bg-brand-50 text-brand-700' : 'text-body hover:bg-subtle hover:text-ink',
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon className={cn('h-[18px] w-[18px]', isActive ? 'text-brand-600' : 'text-muted')} aria-hidden />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function SidebarFooter({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="border-t border-line pt-3">
      <NavLink
        to="/app/about"
        onClick={onNavigate}
        className={({ isActive }) =>
          cn(
            'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium',
            isActive ? 'bg-brand-50 text-brand-700' : 'text-muted hover:bg-subtle hover:text-ink',
          )
        }
      >
        <Info className="h-[18px] w-[18px]" aria-hidden />
        About the project
      </NavLink>
      <p className="mt-3 px-3 text-xs leading-5 text-muted">
        Rule-based NLP · answers are grounded in your uploaded material.
      </p>
    </div>
  );
}

function ServerBanner() {
  const { status, recheck, health } = useServer();
  if (status === 'online' && health?.environment === 'production' && health.database_backend === 'sqlite') {
    return (
      <Alert tone="warning" title="Temporary storage" className="mb-6">
        This deployment is currently using temporary server storage, so uploaded materials and results may be cleared when the
        server restarts.
      </Alert>
    );
  }
  if (status === 'online' || status === 'checking') return null;
  if (status === 'waking') {
    return (
      <Alert tone="info" title="Connecting to the server…" className="mb-6">
        The hosted backend sleeps when idle and can take up to a minute to wake up. Pages will load automatically.
      </Alert>
    );
  }
  return (
    <Alert
      tone={status === 'degraded' ? 'warning' : 'danger'}
      title={status === 'degraded' ? 'The database is unavailable' : 'The server cannot be reached'}
      className="mb-6"
      action={
        <Button size="sm" variant="secondary" onClick={recheck}>
          Retry
        </Button>
      }
    >
      {status === 'degraded'
        ? 'The API is running but cannot reach its database, so your materials cannot be loaded right now.'
        : 'Check your connection or try again shortly.'}
    </Alert>
  );
}

export function AppLayout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-line bg-surface px-3 py-4 lg:flex">
        <Link to="/" className="mb-6 px-2" aria-label="StudyForge AI home">
          <Logo />
        </Link>
        <div className="flex-1">
          <NavItems />
        </div>
        <SidebarFooter />
      </aside>

      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-surface/95 px-4 backdrop-blur lg:hidden">
        <Link to="/" aria-label="StudyForge AI home">
          <Logo />
        </Link>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-md p-2 text-body hover:bg-subtle"
          aria-label="Open navigation"
          aria-expanded={open}
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-navy/40" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] animate-slide-up flex-col bg-surface px-3 py-4 shadow-overlay">
            <div className="mb-6 flex items-center justify-between px-2">
              <Logo />
              <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1.5 hover:bg-subtle" aria-label="Close navigation">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1">
              <NavItems onNavigate={() => setOpen(false)} />
            </div>
            <SidebarFooter onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <main id="main" className="lg:pl-60">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <ServerBanner />
          <Outlet />
        </div>
      </main>
    </div>
  );
}
