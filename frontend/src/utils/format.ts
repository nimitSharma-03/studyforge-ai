import type { Category, Difficulty, QuestionType, QuizMode } from '../types/api';

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(' ');
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string | null | undefined, withTime = false) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  });
}

export function timeAgo(iso: string) {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return formatDate(iso);
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m >= 60) return `${Math.floor(m / 60)} h ${m % 60} min`;
  return m ? `${m} min ${s.toString().padStart(2, '0')} s` : `${s} s`;
}

export function percent(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function locationLabel(type: string, start: number, end?: number) {
  const name = type.charAt(0).toUpperCase() + type.slice(1);
  if (end && end !== start) return `${name}s ${start}–${end}`;
  return `${name} ${start}`;
}

export const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  mcq: 'Multiple choice',
  short_answer: 'Short answer',
  long_answer: 'Long answer',
};

export const CATEGORY_LABEL: Record<Category, string> = {
  definition: 'Definition',
  factual: 'Factual',
  conceptual: 'Conceptual',
  application: 'Application',
  revision: 'Revision',
};

export const DIFFICULTY_LABEL: Record<Difficulty, string> = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };

export const MODE_LABEL: Record<QuizMode, string> = {
  mid_sem: 'Mid-semester',
  end_sem: 'End-semester',
  topic: 'Topic practice',
  custom: 'Custom',
  retry: 'Retry',
};

export const FILE_TYPE_LABEL = { pdf: 'PDF', docx: 'DOCX', pptx: 'PPTX' } as const;

export const optionLetter = (i: number) => String.fromCharCode(65 + i);

export function pluralize(n: number, word: string, plural = `${word}s`) {
  return `${n} ${n === 1 ? word : plural}`;
}
