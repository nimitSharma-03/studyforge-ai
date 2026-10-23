import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Bookmark, BookmarkCheck, Check, Clock, Send } from 'lucide-react';
import { Card, CardBody } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { Alert, ErrorState, PageLoader, ProgressBar } from '../components/ui/Feedback';
import { useApi } from '../hooks/useApi';
import { api, ApiError } from '../services/api';
import type { Quiz, ResponseIn } from '../types/api';
import { DIFFICULTY_LABEL, cn, optionLetter, pluralize } from '../utils/format';

export default function QuizTake() {
  const { quizId = '' } = useParams();
  const quiz = useApi(() => api.quiz(quizId), [quizId]);
  if (quiz.loading) return <PageLoader label="Loading quiz…" />;
  if (quiz.error) return <ErrorState error={quiz.error} onRetry={quiz.error.status === 404 ? undefined : quiz.reload} />;
  if (quiz.data!.status === 'submitted') return <Navigate to={`/app/practice/${quizId}/results`} replace />;
  return <ExamRunner quiz={quiz.data!} />;
}

type Answers = Record<string, { selected: number | null; marked: boolean }>;

function formatClock(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function ExamRunner({ quiz }: { quiz: Quiz }) {
  const navigate = useNavigate();
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Answers>(() =>
    Object.fromEntries(quiz.questions.map((q) => [q.question_id, { selected: q.selected_index, marked: q.marked_for_review }])),
  );
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const [saveState, setSaveState] = useState<'saved' | 'saving' | 'error'>('saved');
  const dirty = useRef(false);
  const submitted = useRef(false);

  const deadline = useMemo(
    () => (quiz.time_limit_minutes ? new Date(quiz.created_at).getTime() + quiz.time_limit_minutes * 60_000 : null),
    [quiz.created_at, quiz.time_limit_minutes],
  );
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!deadline) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [deadline]);
  const remaining = deadline ? Math.max(0, Math.round((deadline - now) / 1000)) : null;

  const responses = useCallback(
    (): ResponseIn[] =>
      quiz.questions.map((q) => ({
        question_id: q.question_id,
        selected_index: answers[q.question_id]?.selected ?? null,
        marked_for_review: answers[q.question_id]?.marked ?? false,
      })),
    [answers, quiz.questions],
  );

  // Autosave shortly after each change so a refresh or lost connection does not lose answers.
  useEffect(() => {
    if (!dirty.current || submitted.current) return;
    setSaveState('saving');
    const t = setTimeout(async () => {
      try {
        await api.saveResponses(quiz.id, responses());
        setSaveState('saved');
      } catch {
        setSaveState('error');
      }
    }, 700);
    return () => clearTimeout(t);
  }, [answers, quiz.id, responses]);

  const submit = useCallback(
    async (auto = false) => {
      if (submitted.current) return;
      submitted.current = true;
      setSubmitting(true);
      setError(undefined);
      try {
        await api.submitQuiz(quiz.id, responses(), Math.round((Date.now() - new Date(quiz.created_at).getTime()) / 1000));
        navigate(`/app/practice/${quiz.id}/results${auto ? '?timeout=1' : ''}`, { replace: true });
      } catch (err) {
        if (err instanceof ApiError && err.code === 'already_submitted') {
          navigate(`/app/practice/${quiz.id}/results`, { replace: true });
          return;
        }
        submitted.current = false;
        setSubmitting(false);
        setError(err instanceof ApiError ? err.message : 'Submission failed. Your answers are still here — try again.');
      }
    },
    [navigate, quiz.created_at, quiz.id, responses],
  );

  useEffect(() => {
    if (remaining === 0) void submit(true);
  }, [remaining, submit]);

  const q = quiz.questions[index];
  const current = answers[q.question_id];
  const answered = quiz.questions.filter((x) => answers[x.question_id]?.selected !== null && answers[x.question_id]?.selected !== undefined).length;
  const marked = quiz.questions.filter((x) => answers[x.question_id]?.marked).length;

  const update = (patch: Partial<{ selected: number | null; marked: boolean }>) => {
    dirty.current = true;
    setAnswers((a) => ({ ...a, [q.question_id]: { ...a[q.question_id], ...patch } }));
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (confirming || (e.target as HTMLElement)?.tagName === 'INPUT') return;
      if (e.key === 'ArrowRight') setIndex((i) => Math.min(quiz.questions.length - 1, i + 1));
      if (e.key === 'ArrowLeft') setIndex((i) => Math.max(0, i - 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [confirming, quiz.questions.length]);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Exam mode</p>
          <h1 className="text-xl font-semibold">{quiz.title}</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted" aria-live="polite">
            {saveState === 'saving' ? 'Saving…' : saveState === 'error' ? 'Not saved — check connection' : 'All answers saved'}
          </span>
          {remaining !== null && (
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 font-mono text-sm font-semibold tabular-nums',
                remaining < 60 ? 'border-danger/40 bg-danger-soft text-danger-ink' : remaining < 300 ? 'border-warning/40 bg-warning-soft text-warning-ink' : 'border-line bg-surface text-ink',
              )}
              role="timer"
              aria-label={`Time remaining ${formatClock(remaining)}`}
            >
              <Clock className="h-4 w-4" aria-hidden />
              {formatClock(remaining)}
            </span>
          )}
          <Button onClick={() => setConfirming(true)} icon={<Send className="h-4 w-4" />} disabled={submitting}>
            Submit
          </Button>
        </div>
      </div>
      <div className="mb-5">
        <div className="mb-1.5 flex justify-between text-xs text-muted">
          <span>
            {answered} of {quiz.total} answered
          </span>
          {marked > 0 && <span>{pluralize(marked, 'question')} marked for review</span>}
        </div>
        <ProgressBar value={answered / Math.max(1, quiz.total)} label="Questions answered" />
      </div>
      {error && <Alert tone="danger" className="mb-4">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-[1fr_240px]">
        <Card>
          <CardBody className="p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-muted">
                Question {index + 1} of {quiz.total}
              </span>
              <Badge>{DIFFICULTY_LABEL[q.difficulty]}</Badge>
              {q.topic_title && <span className="truncate text-xs text-muted">· {q.topic_title}</span>}
            </div>
            <h2 className="mt-4 text-lg font-medium leading-8 text-ink">{q.stem}</h2>
            <div role="radiogroup" aria-label="Answer options" className="mt-5 space-y-2.5">
              {q.options.map((o, i) => {
                const selected = current?.selected === i;
                return (
                  <button
                    key={o}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => update({ selected: selected ? null : i })}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-lg border px-4 py-3 text-left text-[15px] transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
                      selected ? 'border-brand-600 bg-brand-50 text-ink ring-1 ring-brand-600' : 'border-line hover:border-brand-300 hover:bg-subtle/60',
                    )}
                  >
                    <span
                      className={cn(
                        'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold',
                        selected ? 'border-brand-600 bg-brand-600 text-white' : 'border-line-strong text-muted',
                      )}
                    >
                      {selected ? <Check className="h-3.5 w-3.5" /> : optionLetter(i)}
                    </span>
                    <span className="pt-px">{o}</span>
                  </button>
                );
              })}
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
              <Button
                variant={current?.marked ? 'subtle' : 'ghost'}
                onClick={() => update({ marked: !current?.marked })}
                icon={current?.marked ? <BookmarkCheck className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
                aria-pressed={current?.marked}
              >
                {current?.marked ? 'Marked for review' : 'Mark for review'}
              </Button>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={index === 0} onClick={() => setIndex(index - 1)} icon={<ArrowLeft className="h-4 w-4" />}>
                  Previous
                </Button>
                {index < quiz.total - 1 ? (
                  <Button onClick={() => setIndex(index + 1)} className="flex-row-reverse" icon={<ArrowRight className="h-4 w-4" />}>
                    Next
                  </Button>
                ) : (
                  <Button onClick={() => setConfirming(true)} icon={<Send className="h-4 w-4" />}>
                    Finish
                  </Button>
                )}
              </div>
            </div>
          </CardBody>
        </Card>

        <aside>
          <Card>
            <CardBody>
              <p className="mb-3 text-sm font-semibold text-ink">Questions</p>
              <nav aria-label="Question navigation" className="grid grid-cols-6 gap-1.5 lg:grid-cols-5">
                {quiz.questions.map((x, i) => {
                  const a = answers[x.question_id];
                  const isAnswered = a?.selected !== null && a?.selected !== undefined;
                  return (
                    <button
                      key={x.question_id}
                      type="button"
                      onClick={() => setIndex(i)}
                      aria-label={`Question ${i + 1}${isAnswered ? ', answered' : ''}${a?.marked ? ', marked for review' : ''}`}
                      aria-current={i === index ? 'step' : undefined}
                      className={cn(
                        'relative h-9 rounded-md border text-sm font-medium tabular-nums transition-colors',
                        i === index && 'ring-2 ring-brand-500 ring-offset-1',
                        isAnswered ? 'border-brand-600 bg-brand-600 text-white' : 'border-line bg-surface text-body hover:bg-subtle',
                      )}
                    >
                      {i + 1}
                      {a?.marked && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-surface bg-warning" />}
                    </button>
                  );
                })}
              </nav>
              <ul className="mt-4 space-y-1.5 text-xs text-muted">
                <li className="flex items-center gap-2"><span className="h-3 w-3 rounded bg-brand-600" /> Answered</li>
                <li className="flex items-center gap-2"><span className="h-3 w-3 rounded border border-line" /> Not answered</li>
                <li className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-warning" /> Marked for review</li>
              </ul>
            </CardBody>
          </Card>
        </aside>
      </div>

      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Submit your answers?"
        description="You cannot change answers after submitting."
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Keep working
            </Button>
            <Button onClick={() => void submit()} loading={submitting}>
              Submit quiz
            </Button>
          </>
        }
      >
        <ul className="space-y-1 text-sm text-body">
          <li>{answered} of {quiz.total} questions answered</li>
          {quiz.total - answered > 0 && <li className="text-warning-ink">{pluralize(quiz.total - answered, 'question')} unanswered (scored as incorrect)</li>}
          {marked > 0 && <li>{pluralize(marked, 'question')} marked for review</li>}
        </ul>
      </Dialog>
    </div>
  );
}
