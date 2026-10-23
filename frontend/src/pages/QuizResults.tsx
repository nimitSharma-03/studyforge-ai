import { useState } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BookmarkCheck, CheckCircle2, ChevronLeft, CircleDashed, Download, RotateCcw, XCircle } from 'lucide-react';
import { StatCard } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Badge, SourceRef } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Tabs } from '../components/ui/Controls';
import { Alert, ErrorState, PageLoader } from '../components/ui/Feedback';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { api, ApiError } from '../services/api';
import type { QuizResultItem } from '../types/api';
import { MODE_LABEL, cn, formatDate, formatDuration, optionLetter } from '../utils/format';

type Filter = 'all' | 'incorrect' | 'unanswered' | 'marked';

export default function QuizResults() {
  const { quizId = '' } = useParams();
  const [params] = useSearchParams();
  const result = useApi(() => api.quizResult(quizId), [quizId]);
  const [filter, setFilter] = useState<Filter>('all');
  const [retrying, setRetrying] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const navigate = useNavigate();
  const toast = useToast();

  if (result.loading) return <PageLoader label="Loading results…" />;
  if (result.error) {
    if (result.error.code === 'quiz_not_submitted') return <Navigate to={`/app/practice/${quizId}`} replace />;
    return <ErrorState error={result.error} onRetry={result.error.status === 404 ? undefined : result.reload} />;
  }
  const r = result.data!;
  const items = r.items.filter((i) =>
    filter === 'all' ? true : filter === 'marked' ? i.marked_for_review : i.status === filter,
  );
  const missed = r.incorrect_count + r.unanswered_count;
  const chartData = r.topic_breakdown.map((t) => ({
    name: t.topic_title.length > 22 ? `${t.topic_title.slice(0, 21)}…` : t.topic_title,
    full: t.topic_title,
    score: t.total ? Math.round((100 * t.correct) / t.total) : 0,
    label: `${t.correct}/${t.total}`,
  }));

  const retry = async () => {
    setRetrying(true);
    try {
      const quiz = await api.retryQuiz(r.id);
      navigate(`/app/practice/${quiz.id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not start the retry.', 'error');
      setRetrying(false);
    }
  };
  const exportResult = async (format: 'md' | 'txt' | 'pdf') => {
    setExporting(format);
    try {
      await api.exportQuiz(r.id, format);
    } catch (err) {
      toast(err instanceof ApiError ? `Export failed: ${err.message}` : 'Export failed.', 'error');
    } finally {
      setExporting(null);
    }
  };

  return (
    <>
      <Link to="/app/practice" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
        <ChevronLeft className="h-4 w-4" /> Practice Tests
      </Link>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">{MODE_LABEL[r.mode]} · results</p>
          <h1 className="text-2xl font-semibold">{r.title}</h1>
          <p className="mt-1 text-sm text-muted">Submitted {formatDate(r.submitted_at, true)} · scored on the server against the stored answer key</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(['md', 'txt', 'pdf'] as const).map((f) => (
            <Button key={f} size="sm" variant="secondary" loading={exporting === f} onClick={() => exportResult(f)} icon={<Download className="h-3.5 w-3.5" />}>
              {f.toUpperCase()}
            </Button>
          ))}
          {missed > 0 && (
            <Button onClick={retry} loading={retrying} icon={<RotateCcw className="h-4 w-4" />}>
              Retry {missed} missed
            </Button>
          )}
        </div>
      </div>
      {params.get('timeout') && (
        <Alert tone="warning" className="mb-4">
          Time ran out, so the quiz was submitted automatically with the answers you had selected.
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Score" value={`${r.score_percent}%`} hint={`${r.correct_count} of ${r.total} correct`} />
        <StatCard label="Incorrect" value={r.incorrect_count} hint="Answered but wrong" />
        <StatCard label="Unanswered" value={r.unanswered_count} hint="Scored as incorrect" />
        <StatCard
          label="Time taken"
          value={formatDuration(r.duration_seconds)}
          hint={r.time_limit_minutes ? `Limit ${r.time_limit_minutes} min` : 'No time limit'}
        />
      </div>

      {chartData.length > 1 && (
        <Card className="mt-6">
          <CardHeader title="Score by topic" description="Percentage of questions answered correctly in this quiz." />
          <CardBody>
            <div style={{ height: Math.max(160, chartData.length * 44 + 40) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
                  <CartesianGrid horizontal={false} stroke="rgb(var(--line))" />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12, fill: 'rgb(var(--muted))' }} />
                  <YAxis type="category" dataKey="name" width={170} interval={0} tick={{ fontSize: 12, fill: 'rgb(var(--body))' }} />
                  <Tooltip cursor={{ fill: 'rgb(var(--subtle))' }} content={<TopicTooltip />} />
                  <Bar dataKey="score" fill="rgb(var(--brand-600))" radius={[0, 4, 4, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardBody>
        </Card>
      )}

      <div className="mt-8">
        <Tabs
          label="Filter questions"
          value={filter}
          onChange={setFilter}
          tabs={[
            { value: 'all', label: 'All', count: r.total },
            { value: 'incorrect', label: 'Incorrect', count: r.incorrect_count },
            { value: 'unanswered', label: 'Unanswered', count: r.unanswered_count },
            { value: 'marked', label: 'Marked', count: r.items.filter((i) => i.marked_for_review).length },
          ]}
        />
        <div className="mt-5 space-y-4">
          {items.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">No questions in this view.</p>
          ) : (
            items.map((item) => <ReviewItem key={item.question_id} item={item} />)
          )}
        </div>
      </div>
    </>
  );
}

function TopicTooltip({ active, payload }: { active?: boolean; payload?: { payload: { full: string; score: number; label: string } }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-raised">
      <p className="font-medium text-ink">{d.full}</p>
      <p className="text-muted">
        {d.score}% · {d.label} correct
      </p>
    </div>
  );
}

const STATUS = {
  correct: { tone: 'success' as const, label: 'Correct', icon: CheckCircle2 },
  incorrect: { tone: 'danger' as const, label: 'Incorrect', icon: XCircle },
  unanswered: { tone: 'warning' as const, label: 'Unanswered', icon: CircleDashed },
};

export function ReviewItem({ item }: { item: QuizResultItem }) {
  const s = STATUS[item.status];
  const wrongNote = item.selected_index !== null && item.selected_index !== item.correct_index ? item.option_notes?.[item.selected_index] : null;
  return (
    <article className="rounded-lg border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold tabular-nums text-muted">Q{item.position + 1}</span>
        <Badge tone={s.tone} icon={<s.icon className="h-3 w-3" />}>
          {s.label}
        </Badge>
        {item.marked_for_review && (
          <Badge tone="warning" icon={<BookmarkCheck className="h-3 w-3" />}>
            Marked
          </Badge>
        )}
        {item.topic_title && <span className="ml-auto truncate text-xs text-muted">{item.topic_title}</span>}
      </div>
      <p className="mt-3 text-[15px] font-medium leading-7 text-ink">{item.stem}</p>
      <ol className="mt-3 space-y-2">
        {item.options.map((o, i) => {
          const isCorrect = i === item.correct_index;
          const isSelected = i === item.selected_index;
          return (
            <li
              key={o}
              className={cn(
                'flex items-start gap-2 rounded-md border px-3 py-2 text-sm',
                isCorrect && 'border-success/40 bg-success-soft text-success-ink',
                isSelected && !isCorrect && 'border-danger/40 bg-danger-soft text-danger-ink',
                !isCorrect && !isSelected && 'border-line text-body',
              )}
            >
              <span className="font-semibold">{optionLetter(i)}.</span>
              <span className="flex-1">{o}</span>
              {isCorrect && <span className="text-xs font-semibold">Correct answer</span>}
              {isSelected && !isCorrect && <span className="text-xs font-semibold">Your answer</span>}
              {isSelected && isCorrect && <span className="text-xs font-semibold">· Your answer</span>}
            </li>
          );
        })}
      </ol>
      <div className="mt-4 space-y-2 rounded-md bg-subtle/70 p-4 text-sm">
        {wrongNote && (
          <p className="text-danger-ink">
            <span className="font-semibold">Why your answer is wrong: </span>
            {wrongNote}
          </p>
        )}
        <p className="text-body">
          <span className="font-semibold text-ink">Explanation: </span>
          {item.explanation}
        </p>
        <div className="flex items-center gap-2 text-xs text-muted">
          Source <SourceRef type={item.location_type} start={item.location_start} end={item.location_end} />
          <Link to={`/app/learn/${item.document_id}/${item.topic_id ?? ''}`} className="font-medium text-brand-700 hover:underline">
            Revise this topic
          </Link>
        </div>
      </div>
    </article>
  );
}
