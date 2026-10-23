import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CalendarCheck, CalendarRange, Clock, Play, Settings2, Target, Trash2 } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { NoDocuments } from '../components/NoDocuments';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button, ButtonLink, IconButton } from '../components/ui/Button';
import { ChipGroup, Toggle } from '../components/ui/Controls';
import { ErrorState, PageLoader } from '../components/ui/Feedback';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { api, ApiError } from '../services/api';
import type { Difficulty, DocumentSummary, QuizMode } from '../types/api';
import { DIFFICULTY_LABEL, MODE_LABEL, cn, formatDate, pluralize } from '../utils/format';

const MODES: { mode: Exclude<QuizMode, 'retry'>; title: string; icon: typeof Clock; text: string; defaults: { count: number; timer: number | null } }[] = [
  { mode: 'mid_sem', title: 'Mid-semester practice', icon: CalendarRange, text: 'First half of the topics, mostly easy and medium questions.', defaults: { count: 15, timer: 30 } },
  { mode: 'end_sem', title: 'End-semester practice', icon: CalendarCheck, text: 'All topics and all difficulty levels, like a final exam.', defaults: { count: 30, timer: 60 } },
  { mode: 'topic', title: 'Topic practice', icon: Target, text: 'Drill one or more chosen topics without a time limit.', defaults: { count: 10, timer: null } },
  { mode: 'custom', title: 'Custom quiz', icon: Settings2, text: 'Choose topics, difficulty, length and timer yourself.', defaults: { count: 10, timer: null } },
];

export default function PracticeSetup() {
  const docs = useApi(() => api.documents(), []);
  const history = useApi(() => api.quizzes(), []);
  if (docs.loading || history.loading) return <PageLoader />;
  const error = docs.error ?? history.error;
  if (error) return <ErrorState error={error} onRetry={() => { void docs.reload(); void history.reload(); }} />;
  const ready = (docs.data ?? []).filter((d) => d.status === 'ready');
  const header = <PageHeader title="Practice Tests" description="Mock exams scored on the server against stored answer keys. Answers stay hidden until you submit." />;
  if (!ready.length) return (<>{header}<NoDocuments purpose="practice tests" /></>);
  const inProgress = (history.data ?? []).filter((q) => q.status === 'in_progress');
  return (
    <>
      {header}
      {inProgress.length > 0 && (
        <Card className="mb-6">
          <CardHeader title="Continue where you left off" description="Answers are saved automatically while you work." />
          <ul className="divide-y divide-line">
            {inProgress.map((q) => (
              <li key={q.id} className="flex items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-ink">{q.title}</p>
                  <p className="text-xs text-muted">
                    {pluralize(q.total, 'question')} · started {formatDate(q.created_at, true)}
                  </p>
                </div>
                <IconButton
                  label="Discard attempt"
                  onClick={async () => {
                    await api.deleteQuiz(q.id);
                    void history.reload();
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </IconButton>
                <ButtonLink to={`/app/practice/${q.id}`} size="sm">
                  Resume
                </ButtonLink>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <QuizBuilder documents={ready} />
      <RecentAttempts items={(history.data ?? []).filter((q) => q.status === 'submitted').slice(0, 8)} />
    </>
  );
}

function QuizBuilder({ documents }: { documents: DocumentSummary[] }) {
  const [params] = useSearchParams();
  const preselected = documents.find((d) => d.id === params.get('document'))?.id ?? documents[0].id;
  const [mode, setMode] = useState<Exclude<QuizMode, 'retry'>>('mid_sem');
  const [docIds, setDocIds] = useState<string[]>([preselected]);
  const [topicIds, setTopicIds] = useState<string[]>([]);
  const [difficulties, setDifficulties] = useState<Difficulty[]>([]);
  const [count, setCount] = useState(15);
  const [timerOn, setTimerOn] = useState(true);
  const [minutes, setMinutes] = useState(30);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();
  const singleDoc = docIds.length === 1 ? docIds[0] : null;
  const topics = useApi(() => api.topics(singleDoc!), [singleDoc], !!singleDoc && (mode === 'topic' || mode === 'custom'));

  const choose = (m: (typeof MODES)[number]) => {
    setMode(m.mode);
    setCount(m.defaults.count);
    setTimerOn(m.defaults.timer !== null);
    setMinutes(m.defaults.timer ?? 20);
    setTopicIds([]);
    setDifficulties([]);
  };

  const needsTopics = mode === 'topic' || mode === 'custom';
  const canStart = docIds.length > 0 && (mode !== 'topic' || topicIds.length > 0);

  const start = async () => {
    setBusy(true);
    try {
      const quiz = await api.createQuiz({
        mode,
        document_ids: docIds,
        topic_ids: needsTopics ? topicIds.map(Number) : [],
        difficulties: mode === 'custom' ? difficulties : [],
        count,
        time_limit_minutes: timerOn ? minutes : null,
      });
      if (quiz.total < count) toast(`Only ${quiz.total} validated questions matched, so the quiz is shorter than requested.`, 'info');
      navigate(`/app/practice/${quiz.id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not create the quiz.', 'error');
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Start a new test" />
      <CardBody className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {MODES.map((m) => {
            const Icon = m.icon;
            const active = m.mode === mode;
            return (
              <button
                key={m.mode}
                type="button"
                aria-pressed={active}
                onClick={() => choose(m)}
                className={cn(
                  'rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
                  active ? 'border-brand-600 bg-brand-50 ring-1 ring-brand-600' : 'border-line hover:border-brand-300',
                )}
              >
                <Icon className={cn('h-5 w-5', active ? 'text-brand-600' : 'text-muted')} aria-hidden />
                <p className="mt-3 text-sm font-semibold text-ink">{m.title}</p>
                <p className="mt-1 text-xs text-muted">{m.text}</p>
                <p className="mt-2 text-xs font-medium text-body">
                  {m.defaults.count} questions{m.defaults.timer ? ` · ${m.defaults.timer} min` : ''}
                </p>
              </button>
            );
          })}
        </div>

        <ChipGroup
          label="Documents"
          options={documents.map((d) => ({ value: d.id, label: d.name }))}
          value={docIds}
          onChange={(v) => {
            setDocIds(v);
            setTopicIds([]);
          }}
        />

        {needsTopics && (
          <div>
            {!singleDoc ? (
              <p className="text-sm text-muted">Select a single document to choose specific topics{mode === 'custom' ? ', or leave it to cover all topics' : ''}.</p>
            ) : topics.loading ? (
              <p className="text-sm text-muted">Loading topics…</p>
            ) : (
              <ChipGroup
                label={mode === 'topic' ? 'Topics (choose at least one)' : 'Topics (optional — all if none selected)'}
                options={(topics.data ?? []).filter((t) => t.question_count > 0).map((t) => ({ value: String(t.id), label: t.title }))}
                value={topicIds}
                onChange={setTopicIds}
              />
            )}
          </div>
        )}

        {mode === 'custom' && (
          <ChipGroup
            label="Difficulty (optional)"
            options={(['easy', 'medium', 'hard'] as Difficulty[]).map((d) => ({ value: d, label: DIFFICULTY_LABEL[d] }))}
            value={difficulties}
            onChange={setDifficulties}
          />
        )}

        <div className="flex flex-wrap items-end gap-6">
          <div className="w-32">
            <label htmlFor="quiz-count" className="label">
              Questions
            </label>
            <input id="quiz-count" type="number" min={1} max={100} className="field" value={count} onChange={(e) => setCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))} />
          </div>
          <Toggle checked={timerOn} onChange={setTimerOn} label="Exam timer" description="Auto-submits when time runs out" />
          {timerOn && (
            <div className="w-32">
              <label htmlFor="quiz-minutes" className="label">
                Minutes
              </label>
              <input id="quiz-minutes" type="number" min={1} max={240} className="field" value={minutes} onChange={(e) => setMinutes(Math.max(1, Math.min(240, Number(e.target.value) || 1)))} />
            </div>
          )}
          <Button size="lg" className="ml-auto" onClick={start} loading={busy} disabled={!canStart} icon={<Play className="h-4 w-4" />}>
            Start test
          </Button>
        </div>
        <p className="text-xs text-muted">Practice tests use multiple-choice questions only, so they can be scored automatically.</p>
      </CardBody>
    </Card>
  );
}

function RecentAttempts({ items }: { items: Awaited<ReturnType<typeof api.quizzes>> }) {
  if (!items.length) return null;
  return (
    <Card className="mt-6">
      <CardHeader title="Recent results" action={<Link to="/app/progress" className="text-sm font-medium text-brand-700 hover:underline">All history</Link>} />
      <ul className="divide-y divide-line">
        {items.map((q) => (
          <li key={q.id} className="flex items-center gap-3 px-5 py-3">
            <div className="min-w-0 flex-1">
              <Link to={`/app/practice/${q.id}/results`} className="block truncate font-medium text-ink hover:text-brand-700">
                {q.title}
              </Link>
              <p className="text-xs text-muted">
                {MODE_LABEL[q.mode]} · {formatDate(q.submitted_at, true)}
              </p>
            </div>
            <Badge tone={(q.score_percent ?? 0) >= 80 ? 'success' : (q.score_percent ?? 0) >= 60 ? 'info' : 'warning'}>
              {q.correct_count}/{q.total} · {q.score_percent}%
            </Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}
