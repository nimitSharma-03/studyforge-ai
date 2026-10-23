import { useState } from 'react';
import { Link, Outlet } from 'react-router-dom';
import { Github, Menu, X } from 'lucide-react';
import { Logo } from '../components/Logo';
import { ButtonLink } from '../components/ui/Button';
import { GITHUB_URL } from '../config';

const LINKS = [
  { href: '/#features', label: 'Features' },
  { href: '/#how-it-works', label: 'How it works' },
  { href: '/#technology', label: 'Technology' },
  { href: '/#privacy', label: 'Privacy' },
];

export function PublicLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col bg-surface">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/90 backdrop-blur">
        <div className="container-page flex h-16 items-center justify-between">
          <Link to="/" aria-label="StudyForge AI home">
            <Logo />
          </Link>
          <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <a key={l.href} href={l.href} className="rounded-md px-3 py-2 text-sm font-medium text-body hover:text-ink">
                {l.label}
              </a>
            ))}
            <Link to="/about" className="rounded-md px-3 py-2 text-sm font-medium text-body hover:text-ink">
              About
            </Link>
          </nav>
          <div className="hidden items-center gap-2 md:flex">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="rounded-md p-2 text-muted hover:bg-subtle hover:text-ink"
              aria-label="Source code on GitHub"
            >
              <Github className="h-5 w-5" />
            </a>
            <ButtonLink to="/app">Open app</ButtonLink>
          </div>
          <button
            type="button"
            className="rounded-md p-2 md:hidden"
            onClick={() => setOpen((o) => !o)}
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open && (
          <div className="border-t border-line bg-surface md:hidden">
            <nav aria-label="Mobile" className="container-page flex flex-col py-3">
              {LINKS.map((l) => (
                <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="rounded-md px-2 py-2 text-sm font-medium">
                  {l.label}
                </a>
              ))}
              <Link to="/about" onClick={() => setOpen(false)} className="rounded-md px-2 py-2 text-sm font-medium">
                About
              </Link>
              <ButtonLink to="/app" className="mt-2">
                Open app
              </ButtonLink>
            </nav>
          </div>
        )}
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-canvas">
        <div className="container-page flex flex-col gap-6 py-10 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-3 text-sm text-muted">
              StudyForge AI: An NLP-Based Personalized Learning and Examination Preparation Platform. Built as an academic NLP
              lab project.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-8 text-sm">
            <div>
              <p className="font-semibold text-ink">Product</p>
              <ul className="mt-2 space-y-1.5 text-muted">
                <li><Link to="/app" className="hover:text-ink">Open the app</Link></li>
                <li><a href="/#features" className="hover:text-ink">Features</a></li>
                <li><a href="/#privacy" className="hover:text-ink">Privacy</a></li>
              </ul>
            </div>
            <div>
              <p className="font-semibold text-ink">Project</p>
              <ul className="mt-2 space-y-1.5 text-muted">
                <li><Link to="/about" className="hover:text-ink">About & methodology</Link></li>
                <li><a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-ink">GitHub repository</a></li>
                <li><a href={`${GITHUB_URL}/blob/main/LICENSE`} target="_blank" rel="noreferrer" className="hover:text-ink">MIT License</a></li>
              </ul>
            </div>
          </div>
        </div>
        <div className="border-t border-line">
          <p className="container-page py-4 text-xs text-muted">
            © {new Date().getFullYear()} StudyForge AI. Study aid only — it does not guarantee examination results.
          </p>
        </div>
      </footer>
    </div>
  );
}
