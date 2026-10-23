import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BarChart3, ClipboardCheck, Gauge, History, Target, Trash2 } from 'lucide-react';
import { PageHeader, StatCard } from '../components/PageHeader';
import { RecommendationList } from '../components/Recommendations';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Badge, SourceRef, type Tone } from '../components/ui/Badge';
import { Button, ButtonLink } from '../components/ui/Button';
import { Tabs } from '../components/ui/Controls';
import { Dialog } from '../components/ui/Dialog';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, PageLoader, ProgressBar } from '../components/ui/Feedback';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { api, ApiError } from '../services/api';
import type { TopicProgress, TopicStatus } from '../types/api';
import { MODE_LABEL, formatDate, formatDuration, optionLetter, percent } from '../utils/format';

const STATUS: Record<TopicStatus, { tone: Tone; label: string }> = {
  not_started: { tone: 'neutral', label: 'Not practised' },
  insufficient: { tone: 'info', label: 'Needs more practice' },
  weak: { tone: 'danger', label: 'Weak' },
  developing: { tone: 'warning', label: 'Developing' },
  strong: { tone: 'success', label: 'Strong' },
};

type View = 'topics' | 'incorrect' | 'history';

export default function Progress() {
  const summary = useApi(() => api.progress(), []);
  const history = useApi(() => api.quizzes(), []);
  const incorrect = useApi(() => api.incorrect(), []);
  const [view, setView] = useState<View>('topics');

  if (summary.loading || history.loading || incorrect.loading) return <PageLoader label="Loading progress…" />;
  const error = summary.error ?? history.error ?? incorrect.error;
  if (error) return <ErrorState error={error} onRetry={() => { void summary.reload(); void history.reload(); void incorrect.reload(); }} />;
  const p = summary.data!;
  const submitted = (history.data ?? []).filter((h) => h.status === 'submitted');

  const header = <PageHeader title="Progress & Revision" description="Calculated only from quizzes you have submitted. Nothing here is estimated." />;
  if (p.attempts_submitted === 0) {
    return (
      <>
        {header}
        <EmptyState
          icon={<BarChart3 className="h-5 w-5" />}
          title="No quiz attempts yet"
          description="Submit a practice test to see accuracy by topic, weak areas and questions to revisit."
          action={<ButtonLink to="/app/practice" icon={<ClipboardCheck className="h-4 w-4" />}>Take a practice test</ButtonLink>}
        />
      </>
    );
  }
  const trend = p.accuracy_trend.map((t, i) => ({ n: i + 1, score: t.score_percent, title: t.title, at: formatDate(t.submitted_at, true) }));

  return (
    <>
      {header}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Quizzes submitted" value={p.attempts_submitted} icon={<History className="h-4 w-4" />} />
        <StatCard label="Questions attempted" value={p.questions_answered} hint={`${p.questions_correct} correct`} icon={<ClipboardCheck className="h-4 w-4" />} />
        <StatCard
          label="Overall accuracy"
          value={p.average_accuracy === null ? '—' : percent(p.average_accuracy)}
          hint={p.average_accuracy === null ? `Needs ${p.min_answers_for_accuracy}+ attempted questions` : 'Unanswered questions count as incorrect'}
          icon={<Gauge className="h-4 w-4" />}
        />
        <StatCard label="Weak topics" value={p.weak_topics.length} hint={`Below 60% over ${p.min_answers_per_topic}+ questions`} icon={<Target className="h-4 w-4" />} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="self-start lg:col-span-2">
          <CardHeader title="Score trend" description="Score of each submitted quiz, oldest to newest (last 15)." />
          <CardBody>
            {trend.length < 2 ? (
              <p className="py-8 text-center text-sm text-muted">Submit at least two quizzes to see a trend.</p>
            ) : (
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ left: -12, right: 12, top: 8, bottom: 0 }}>
                    <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
                    <XAxis dataKey="n" tick={{ fontSize: 12, fill: 'rgb(var(--muted))' }} tickFormatter={(v) => `#${v}`} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: 'rgb(var(--muted))' }} tickFormatter={(v) => `${v}%`} />
                    <Tooltip formatter={(v) => [`${v}%`, 'Score'] as [string, string]} labelFormatter={(_l, pl) => (pl?.[0] ? `${pl[0].payload.title} · ${pl[0].payload.at}` : '')} />
                    <Line type="monotone" dataKey="score" stroke="rgb(var(--brand-600))" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Revision plan" />
          <CardBody>
            <RecommendationList items={p.recommendations} />
          </CardBody>
        </Card>
      </div>

      <div className="mt-8">
        <Tabs
          label="Progress views"
          value={view}
          onChange={setView}
          tabs={[
            { value: 'topics', label: 'Accuracy by topic', count: p.topics.length },
            { value: 'incorrect', label: 'Incorrect questions', count: incorrect.data?.length ?? 0 },
            { value: 'history', label: 'Quiz history', count: submitted.length },
          ]}
        />
        <div className="mt-5">
          {view === 'topics' && <TopicTable topics={p.topics} minAnswers={p.min_answers_per_topic} />}
          {view === 'incorrect' && <IncorrectList items={incorrect.data ?? []} />}
          {view === 'history' && <HistoryTable items={submitted} onDeleted={() => { void history.reload(); void summary.reload(); void incorrect.reload(); }} />}
        </div>
      </div>
      <PrivacyCard />
    </>
  );
}

function TopicTable({ topics, minAnswers }: { topics: TopicProgress[]; minAnswers: number }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line bg-subtle/60 text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-5 py-2.5 font-medium">Topic</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="w-48 px-3 py-2.5 font-medium">Accuracy</th>
              <th className="px-3 py-2.5 font-medium">Attempted</th>
              <th className="px-5 py-2.5 font-medium">Last practised</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {topics.map((t) => (
              <tr key={t.topic_id}>
                <td className="px-5 py-3">
                  <Link to={`/app/learn/${t.document_id}/${t.topic_id}`} className="font-medium text-ink hover:text-brand-700">
                    {t.topic_title}
                  </Link>
                  <p className="text-xs text-muted">{t.document_name}</p>
                </td>
                <td className="px-3 py-3"><Badge tone={STATUS[t.status].tone}>{STATUS[t.status].label}</Badge></td>
                <td className="px-3 py-3">
                  {t.accuracy === null ? (
                    <span className="text-muted">—</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <ProgressBar
                        value={t.accuracy}
                        tone={t.status === 'weak' ? 'danger' : t.status === 'strong' ? 'success' : t.status === 'developing' ? 'warning' : 'brand'}
                        label={`${t.topic_title} accuracy`}
                      />
                      <span className="w-10 text-right tabular-nums text-body">{percent(t.accuracy)}</span>
                    </div>
                  )}
                </td>
                <td className="px-3 py-3 tabular-nums text-body">{t.correct}/{t.attempted}</td>
                <td className="px-5 py-3 text-muted">{t.last_practiced ? formatDate(t.last_practiced) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-5 py-3 text-xs text-muted">
        A topic is rated weak, developing or strong only after {minAnswers} or more attempted questions; below that it is shown as
        needing more practice.
      </p>
    </Card>
  );
}

function IncorrectList({ items }: { items: Awaited<ReturnType<typeof api.incorrect>> }) {
  if (!items.length) {
    return <EmptyState compact title="Nothing to review" description="Questions you answer incorrectly appear here until you answer them correctly in a later quiz." />;
  }
  return (
    <div className="space-y-4">
      {items.map((i) => (
        <article key={i.question_id} className="rounded-lg border border-line bg-surface p-5 shadow-card">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <Badge tone={i.selected_index === null ? 'warning' : 'danger'}>{i.selected_index === null ? 'Unanswered' : 'Incorrect'}</Badge>
            {i.times_missed > 1 && <Badge>Missed {i.times_missed}×</Badge>}
            <span>{i.topic_title}</span>
            <span className="ml-auto">{i.attempt_title} · {formatDate(i.answered_at)}</span>
          </div>
          <p className="mt-3 font-medium text-ink">{i.stem}</p>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            {i.selected_index !== null && (
              <p className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-danger-ink">
                <span className="font-semibold">Your answer: </span>
                {optionLetter(i.selected_index)}. {i.options[i.selected_index]}
              </p>
            )}
            <p className="rounded-md border border-success/30 bg-success-soft px-3 py-2 text-success-ink">
              <span className="font-semibold">Correct: </span>
              {optionLetter(i.correct_index)}. {i.options[i.correct_index]}
            </p>
          </div>
          <p className="mt-3 text-sm text-body">{i.explanation}</p>
          <div className="mt-2 flex items-center gap-2">
            <SourceRef type={i.location_type} start={i.location_start} />
            <Link to={`/app/learn/${i.document_id}/${i.topic_id ?? ''}`} className="text-xs font-medium text-brand-700 hover:underline">
              Revise topic
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}

function HistoryTable({ items, onDeleted }: { items: Awaited<ReturnType<typeof api.quizzes>>; onDeleted: () => void }) {
  const toast = useToast();
  const remove = async (id: string) => {
    try {
      await api.deleteQuiz(id);
      toast('Quiz attempt deleted.');
      onDeleted();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not delete the attempt.', 'error');
    }
  };
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line bg-subtle/60 text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-5 py-2.5 font-medium">Quiz</th>
              <th className="px-3 py-2.5 font-medium">Mode</th>
              <th className="px-3 py-2.5 font-medium">Score</th>
              <th className="px-3 py-2.5 font-medium">Time</th>
              <th className="px-3 py-2.5 font-medium">Submitted</th>
              <th className="px-5 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {items.map((h) => (
              <tr key={h.id}>
                <td className="px-5 py-3">
                  <Link to={`/app/practice/${h.id}/results`} className="font-medium text-ink hover:text-brand-700">{h.title}</Link>
                </td>
                <td className="px-3 py-3 text-body">{MODE_LABEL[h.mode]}</td>
                <td className="px-3 py-3 tabular-nums text-body">{h.correct_count}/{h.total} ({h.score_percent}%)</td>
                <td className="px-3 py-3 text-body">{formatDuration(h.duration_seconds)}</td>
                <td className="px-3 py-3 text-muted">{formatDate(h.submitted_at, true)}</td>
                <td className="px-5 py-3 text-right">
                  <button type="button" onClick={() => remove(h.id)} className="text-muted hover:text-danger" aria-label={`Delete ${h.title}`}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PrivacyCard() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const wipe = async () => {
    setBusy(true);
    try {
      await api.deleteWorkspace();
      window.location.assign('/app');
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not delete your data.', 'error');
      setBusy(false);
    }
  };
  return (
    <Card className="mt-10">
      <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-ink">Your data</p>
          <p className="text-xs text-muted">
            Your materials and results are tied to an anonymous workspace stored in this browser. Delete everything at any time.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setOpen(true)} icon={<Trash2 className="h-4 w-4" />}>
          Delete all my data
        </Button>
      </CardBody>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Delete all your data?"
        description="All documents, extracted text, questions, quiz attempts and progress in this workspace will be permanently deleted."
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button variant="danger" onClick={wipe} loading={busy}>Delete everything</Button>
          </>
        }
      />
    </Card>
  );
}
