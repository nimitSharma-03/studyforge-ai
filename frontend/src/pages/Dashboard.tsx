import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BookOpenText,
  ClipboardCheck,
  FileText,
  FlaskConical,
  Gauge,
  History,
  RotateCcw,
  Target,
  Upload,
} from 'lucide-react';
import { PageHeader, StatCard } from '../components/PageHeader';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import { Badge, StatusDot } from '../components/ui/Badge';
import { Button, ButtonLink } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, PageLoader, ProgressBar } from '../components/ui/Feedback';
import { RecommendationList } from '../components/Recommendations';
import { useApi } from '../hooks/useApi';
import { useLoadSample } from '../hooks/useLoadSample';
import { api } from '../services/api';
import { FILE_TYPE_LABEL, percent, pluralize, timeAgo } from '../utils/format';

export default function Dashboard() {
  const docs = useApi(() => api.documents(), []);
  const progress = useApi(() => api.progress(), []);
  const sample = useLoadSample();

  if (docs.loading || progress.loading) return <PageLoader label="Loading your dashboard…" />;
  const error = docs.error ?? progress.error;
  if (error)
    return (
      <ErrorState
        error={error}
        onRetry={() => {
          void docs.reload();
          void progress.reload();
        }}
      />
    );
  const documents = docs.data ?? [];
  const p = progress.data!;

  if (documents.length === 0) {
    return (
      <>
        <PageHeader title="Welcome to StudyForge" description="Upload your lecture notes to get topics, learning guides and practice tests." />
        <EmptyState
          illustration
          title="No study material yet"
          description="Upload a PDF, Word document or PowerPoint deck with selectable text. You can also explore the app with a short demonstration document about NLP fundamentals."
          action={
            <>
              <ButtonLink to="/app/upload" icon={<Upload className="h-4 w-4" />}>
                Upload material
              </ButtonLink>
              <Button variant="secondary" onClick={sample.load} loading={sample.loading} icon={<FlaskConical className="h-4 w-4" />}>
                Try the demo notes
              </Button>
            </>
          }
        />
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            { icon: Upload, title: '1. Upload', text: 'Text, headings and page or slide numbers are extracted.' },
            { icon: BookOpenText, title: '2. Learn', text: 'Read topic-wise guides and ask questions about your notes.' },
            { icon: ClipboardCheck, title: '3. Practise', text: 'Take mock exams and track accuracy by topic.' },
          ].map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-lg border border-line bg-surface p-4">
              <Icon className="h-5 w-5 text-brand-600" aria-hidden />
              <p className="mt-2 font-medium text-ink">{title}</p>
              <p className="text-sm text-muted">{text}</p>
            </div>
          ))}
        </div>
      </>
    );
  }

  const recent = documents.slice(0, 5);
  const revision = p.weak_topics.slice(0, 5);
  return (
    <>
      <PageHeader
        title="Welcome back"
        description="Here is where your preparation stands, based on your uploaded material and submitted quizzes."
        actions={
          <>
            <ButtonLink to="/app/upload" variant="secondary" icon={<Upload className="h-4 w-4" />}>
              Upload material
            </ButtonLink>
            <ButtonLink to="/app/practice" icon={<ClipboardCheck className="h-4 w-4" />}>
              Start practice
            </ButtonLink>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Documents processed"
          value={p.documents_ready}
          hint={p.documents_total > p.documents_ready ? `${p.documents_total - p.documents_ready} failed or pending` : 'Ready to study'}
          icon={<FileText className="h-4 w-4" />}
        />
        <StatCard
          label="Quiz attempts"
          value={p.attempts_submitted}
          hint={p.attempts_in_progress ? `${p.attempts_in_progress} in progress` : 'Submitted'}
          icon={<History className="h-4 w-4" />}
        />
        <StatCard
          label="Average accuracy"
          value={p.average_accuracy === null ? '—' : percent(p.average_accuracy)}
          hint={
            p.average_accuracy === null
              ? `Shown after ${p.min_answers_for_accuracy}+ answered questions`
              : `${p.questions_correct} of ${p.questions_answered} questions correct`
          }
          icon={<Gauge className="h-4 w-4" />}
        />
        <StatCard
          label="Topics needing revision"
          value={p.weak_topics.length}
          hint={`Below 60% with ${p.min_answers_per_topic}+ attempts`}
          icon={<Target className="h-4 w-4" />}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader
              title="Recent materials"
              action={
                <Link to="/app/materials" className="text-sm font-medium text-brand-700 hover:underline">
                  View all
                </Link>
              }
            />
            <ul className="divide-y divide-line">
              {recent.map((d) => (
                <li key={d.id} className="flex items-center gap-4 px-5 py-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-subtle text-2xs font-semibold text-muted">
                    {FILE_TYPE_LABEL[d.file_type]}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link to={`/app/materials/${d.id}`} className="block truncate font-medium text-ink hover:text-brand-700">
                      {d.name}
                    </Link>
                    <p className="text-xs text-muted">
                      {d.status === 'ready'
                        ? `${pluralize(d.topic_count, 'topic')} · ${pluralize(d.question_count, 'question')} · ${timeAgo(d.created_at)}`
                        : d.status === 'failed'
                          ? 'Processing failed'
                          : 'Processing'}
                    </p>
                  </div>
                  {d.status === 'ready' ? (
                    <ButtonLink to={`/app/learn/${d.id}`} size="sm" variant="ghost">
                      Study <ArrowRight className="h-3.5 w-3.5" />
                    </ButtonLink>
                  ) : (
                    <Badge tone={d.status === 'failed' ? 'danger' : 'info'}>{d.status === 'failed' ? 'Failed' : 'Processing'}</Badge>
                  )}
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardHeader
              title="Topics requiring revision"
              description="Identified from your quiz answers — never estimated."
              action={
                <Link to="/app/progress" className="text-sm font-medium text-brand-700 hover:underline">
                  Progress
                </Link>
              }
            />
            <CardBody>
              {revision.length === 0 ? (
                <p className="text-sm text-muted">
                  {p.attempts_submitted === 0
                    ? 'Take a practice test to find out which topics need more work.'
                    : `No weak topics yet. A topic is flagged when its accuracy is below 60% across at least ${p.min_answers_per_topic} attempted questions.`}
                </p>
              ) : (
                <ul className="space-y-3">
                  {revision.map((t) => (
                    <li key={t.topic_id} className="flex items-center gap-4">
                      <div className="min-w-0 flex-1">
                        <Link to={`/app/learn/${t.document_id}/${t.topic_id}`} className="block truncate text-sm font-medium text-ink hover:text-brand-700">
                          {t.topic_title}
                        </Link>
                        <ProgressBar value={t.accuracy ?? 0} tone="danger" className="mt-1.5" label={`${t.topic_title} accuracy`} />
                      </div>
                      <span className="w-20 text-right text-sm tabular-nums text-muted">
                        {t.correct}/{t.attempted}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Suggested next steps" />
            <CardBody>
              <RecommendationList items={p.recommendations.slice(0, 4)} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Recent activity" />
            <CardBody>
              {p.recent_activity.length === 0 ? (
                <p className="text-sm text-muted">No activity yet.</p>
              ) : (
                <ol className="space-y-3">
                  {p.recent_activity.map((a) => (
                    <li key={`${a.kind}-${a.ref_id}`} className="flex gap-3 text-sm">
                      <span className="mt-1.5">
                        <StatusDot tone={a.kind === 'quiz' ? 'brand' : 'success'} />
                      </span>
                      <div className="min-w-0">
                        <Link
                          to={a.kind === 'quiz' ? `/app/practice/${a.ref_id}/results` : `/app/materials/${a.ref_id}`}
                          className="block truncate font-medium text-ink hover:text-brand-700"
                        >
                          {a.title}
                        </Link>
                        <p className="text-xs text-muted">
                          {a.kind === 'quiz' ? 'Quiz · ' : 'Upload · '}
                          {a.detail} · {timeAgo(a.at)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </CardBody>
          </Card>
          {p.attempts_submitted > 0 && (
            <ButtonLink to="/app/progress" variant="subtle" className="w-full" icon={<RotateCcw className="h-4 w-4" />}>
              Review incorrect answers
            </ButtonLink>
          )}
        </div>
      </div>
    </>
  );
}
