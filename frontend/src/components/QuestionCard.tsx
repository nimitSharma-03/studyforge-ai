import { useState } from 'react';
import { CheckCircle2, ChevronDown, Eye } from 'lucide-react';
import type { Question } from '../types/api';
import { Badge, SourceRef } from './ui/Badge';
import { CATEGORY_LABEL, DIFFICULTY_LABEL, QUESTION_TYPE_LABEL, cn, optionLetter } from '../utils/format';

const difficultyTone = { easy: 'success', medium: 'info', hard: 'warning' } as const;

/** Study-mode question: the answer and explanation are revealed on demand. */
export function QuestionCard({ q, index, revealAll }: { q: Question; index: number; revealAll: boolean }) {
  const [revealed, setRevealed] = useState(false);
  const show = revealAll || revealed;
  return (
    <article className="rounded-lg border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-sm font-semibold tabular-nums text-muted">Q{index}</span>
        <Badge tone="brand">{QUESTION_TYPE_LABEL[q.question_type]}</Badge>
        <Badge tone={difficultyTone[q.difficulty]}>{DIFFICULTY_LABEL[q.difficulty]}</Badge>
        <Badge>{CATEGORY_LABEL[q.category]}</Badge>
        {q.topic_title && <span className="ml-auto truncate text-xs text-muted">{q.topic_title}</span>}
      </div>
      <p className="mt-3 text-[15px] font-medium leading-7 text-ink">{q.stem}</p>
      {q.options && (
        <ol className="mt-3 grid gap-2 sm:grid-cols-2">
          {q.options.map((o, i) => {
            const correct = show && i === q.correct_index;
            return (
              <li
                key={o}
                className={cn(
                  'flex items-start gap-2 rounded-md border px-3 py-2 text-sm',
                  correct ? 'border-success/40 bg-success-soft text-success-ink' : 'border-line text-body',
                )}
              >
                <span className="font-semibold">{optionLetter(i)}.</span>
                <span className="flex-1">{o}</span>
                {correct && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-label="Correct answer" />}
              </li>
            );
          })}
        </ol>
      )}
      {!revealAll && (
        <button
          type="button"
          onClick={() => setRevealed((r) => !r)}
          aria-expanded={revealed}
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
        >
          {revealed ? <ChevronDown className="h-4 w-4 rotate-180" /> : <Eye className="h-4 w-4" />}
          {revealed ? 'Hide answer' : q.question_type === 'mcq' ? 'Show answer' : 'Show model answer'}
        </button>
      )}
      {show && (
        <div className="mt-4 space-y-3 rounded-md bg-subtle/70 p-4 text-sm">
          {q.question_type !== 'mcq' && (
            <div>
              <p className="font-semibold text-ink">Model answer</p>
              <div className="mt-1 whitespace-pre-line text-body">{q.answer_text}</div>
            </div>
          )}
          <div>
            <p className="font-semibold text-ink">Explanation</p>
            <p className="mt-1 text-body">{q.explanation}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>Source</span>
            <SourceRef type={q.location_type} start={q.location_start} end={q.location_end} />
          </div>
        </div>
      )}
    </article>
  );
}
