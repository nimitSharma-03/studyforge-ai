import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  BookOpenText,
  Download,
  FileSearch,
  Lightbulb,
  Link2,
  MessageSquareText,
  Quote,
  Send,
  Sparkles,
} from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { NoDocuments } from '../components/NoDocuments';
import { Card, CardBody } from '../components/ui/Card';
import { Badge, SourceRef } from '../components/ui/Badge';
import { Button, ButtonLink } from '../components/ui/Button';
import { Segmented, Select, Tabs } from '../components/ui/Controls';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert, ErrorState, PageLoader, Skeleton, Spinner } from '../components/ui/Feedback';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { useServer } from '../hooks/useServer';
import { api, ApiError, type ExportFormat } from '../services/api';
import type { AskResponse, GuideItem, LLMExplanation, TopicDetail, TopicSummary } from '../types/api';
import { cn, locationLabel, pluralize } from '../utils/format';

type Tab = 'guide' | 'source' | 'ask';
type Mode = 'concise' | 'detailed';

export default function Learn() {
  const { documentId, topicId } = useParams();
  const docs = useApi(() => api.documents(), []);
  if (docs.loading) return <PageLoader label="Loading materials…" />;
  if (docs.error) return <ErrorState error={docs.error} onRetry={docs.reload} />;
  const ready = (docs.data ?? []).filter((d) => d.status === 'ready');
  if (!ready.length) {
    return (
      <>
        <PageHeader title="Learn" description="Topic-wise learning guides built from your material." />
        <NoDocuments purpose="learning guides" />
      </>
    );
  }
  if (!documentId) return <Navigate to={`/app/learn/${ready[0].id}`} replace />;
  return <DocumentLearn key={documentId} documentId={documentId} topicId={topicId ? Number(topicId) : undefined} documents={ready} />;
}

function DocumentLearn({
  documentId,
  topicId,
  documents,
}: {
  documentId: string;
  topicId?: number;
  documents: { id: string; name: string }[];
}) {
  const topics = useApi(() => api.topics(documentId), [documentId]);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = (params.get('tab') as Tab) || 'guide';
  const setTab = (t: Tab) => setParams((p) => { p.set('tab', t); return p; }, { replace: true });

  if (topics.loading) return <PageLoader label="Loading topics…" />;
  if (topics.error) return <ErrorState error={topics.error} onRetry={topics.reload} />;
  const list = topics.data ?? [];
  if (!list.length) {
    return <EmptyState icon={<FileSearch className="h-5 w-5" />} title="No topics found" description="This document did not produce any topics." />;
  }
  const activeId = topicId && list.some((t) => t.id === topicId) ? topicId : list[0].id;
  if (!topicId) return <Navigate to={`/app/learn/${documentId}/${activeId}${params.toString() ? `?${params}` : ''}`} replace />;
  const docName = documents.find((d) => d.id === documentId)?.name ?? 'Document';

  return (
    <>
      <PageHeader
        eyebrow="Learn"
        title={docName}
        actions={
          documents.length > 1 ? (
            <div className="w-64">
              <Select aria-label="Choose document" value={documentId} onChange={(e) => navigate(`/app/learn/${e.target.value}`)}>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </div>
          ) : undefined
        }
      />
      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <TopicNav topics={list} documentId={documentId} activeId={activeId} tab={tab} />
        <TopicView key={activeId} topicId={activeId} documentId={documentId} tab={tab} setTab={setTab} />
      </div>
    </>
  );
}

function TopicNav({ topics, documentId, activeId, tab }: { topics: TopicSummary[]; documentId: string; activeId: number; tab: Tab }) {
  const navigate = useNavigate();
  return (
    <>
      <div className="lg:hidden">
        <label htmlFor="topic-select" className="label">
          Topic
        </label>
        <Select id="topic-select" value={activeId} onChange={(e) => navigate(`/app/learn/${documentId}/${e.target.value}?tab=${tab}`)}>
          {topics.map((t) => (
            <option key={t.id} value={t.id}>
              {t.position + 1}. {t.title}
            </option>
          ))}
        </Select>
      </div>
      <nav aria-label="Topics" className="hidden lg:block">
        <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wide text-muted">{pluralize(topics.length, 'topic')}</p>
        <ol className="sticky top-6 max-h-[calc(100vh-8rem)] space-y-0.5 overflow-y-auto pr-1">
          {topics.map((t) => (
            <li key={t.id}>
              <Link
                to={`/app/learn/${documentId}/${t.id}?tab=${tab}`}
                aria-current={t.id === activeId ? 'page' : undefined}
                className={cn(
                  'flex gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                  t.id === activeId ? 'bg-brand-50 font-medium text-brand-700' : 'text-body hover:bg-subtle hover:text-ink',
                )}
              >
                <span className="w-5 shrink-0 tabular-nums text-muted">{t.position + 1}.</span>
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2">{t.title}</span>
                  <span className="mt-0.5 block text-xs font-normal text-muted">
                    {locationLabel(t.location_type, t.location_start, t.location_end)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </nav>
    </>
  );
}

function TopicView({ topicId, documentId, tab, setTab }: { topicId: number; documentId: string; tab: Tab; setTab: (t: Tab) => void }) {
  const topic = useApi(() => api.topic(topicId), [topicId]);
  const [mode, setMode] = useState<Mode>('concise');
  if (topic.loading)
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  if (topic.error) return <ErrorState error={topic.error} onRetry={topic.reload} />;
  const t = topic.data!;
  return (
    <div className="min-w-0">
      <div className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <SourceRef type={t.location_type} start={t.location_start} end={t.location_end} />
          <span className="text-xs text-muted">
            {t.word_count.toLocaleString()} words · {pluralize(t.question_count, 'question')}
          </span>
        </div>
        <h2 className="mt-2 text-xl font-semibold">{t.title}</h2>
        {t.keywords.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {t.keywords.slice(0, 8).map((k) => (
              <Badge key={k} tone="brand">
                {k}
              </Badge>
            ))}
          </div>
        )}
      </div>
      <Tabs
        label="Topic views"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: 'guide', label: 'Learning guide' },
          { value: 'source', label: 'Source material', count: t.chunks.length },
          { value: 'ask', label: 'Ask your notes' },
        ]}
      />
      <div className="mt-5">
        {tab === 'guide' && <GuideView topic={t} mode={mode} setMode={setMode} documentId={documentId} />}
        {tab === 'source' && <SourceView topic={t} />}
        {tab === 'ask' && <AskPanel documentId={documentId} topic={t} />}
      </div>
      <div className="mt-8 flex justify-between gap-3 border-t border-line pt-4">
        {t.prev_topic_id ? (
          <ButtonLink to={`/app/learn/${documentId}/${t.prev_topic_id}?tab=${tab}`} variant="ghost" icon={<ArrowLeft className="h-4 w-4" />}>
            Previous topic
          </ButtonLink>
        ) : <span />}
        {t.next_topic_id && (
          <ButtonLink to={`/app/learn/${documentId}/${t.next_topic_id}?tab=${tab}`} variant="ghost" className="flex-row-reverse" icon={<ArrowRight className="h-4 w-4" />}>
            Next topic
          </ButtonLink>
        )}
      </div>
    </div>
  );
}

function Cited({ item, type, children }: { item: GuideItem; type: string; children?: ReactNode }) {
  return (
    <>
      {children ?? item.text} <SourceRef type={type} start={item.location} className="ml-0.5 align-middle" />
    </>
  );
}

function Section({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold">
        <span className="text-brand-600">{icon}</span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function GuideView({ topic, mode, setMode, documentId }: { topic: TopicDetail; mode: Mode; setMode: (m: Mode) => void; documentId: string }) {
  const g = topic.guide;
  const type = topic.unit_label;
  const toast = useToast();
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const points = mode === 'concise' ? g.key_points.filter((p) => (p.rank ?? 0) < 5) : g.key_points;
  const empty = !g.overview.length && !g.key_points.length && !g.definitions.length;

  const exportNotes = async (format: ExportFormat) => {
    setExporting(format);
    try {
      await api.exportNotes(documentId, format, mode);
    } catch (err) {
      toast(err instanceof ApiError ? `Export failed: ${err.message}` : 'Export failed.', 'error');
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Guide detail"
          value={mode}
          onChange={setMode}
          options={[
            { value: 'concise', label: 'Concise revision' },
            { value: 'detailed', label: 'Detailed study' },
          ]}
        />
        <div className="flex items-center gap-1">
          <span className="mr-1 text-xs text-muted">Revision notes (all topics):</span>
          {(['md', 'txt', 'pdf'] as const).map((f) => (
            <Button key={f} size="sm" variant="secondary" loading={exporting === f} onClick={() => exportNotes(f)} icon={<Download className="h-3.5 w-3.5" />}>
              {f.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted">
        Extractive guide: every sentence is quoted from your material and selected by rule-based NLP (TF-IDF centrality, definition
        patterns and cue phrases). Nothing here is paraphrased or generated by a language model.
      </p>

      {empty ? (
        <Alert tone="info" title="Not enough text for a guide">
          This topic has too little prose to build a guide. Read the source material instead.
        </Alert>
      ) : (
        <Card>
          <CardBody className="space-y-7 py-6">
            {g.overview.length > 0 && (
              <Section title="Overview" icon={<BookOpenText className="h-4 w-4" />}>
                <div className="space-y-2 text-[15px] leading-7 text-body">
                  {g.overview.map((o) => (
                    <p key={o.text}>
                      <Cited item={o} type={type} />
                    </p>
                  ))}
                </div>
              </Section>
            )}
            {g.definitions.length > 0 && (
              <Section title="Definitions" icon={<Quote className="h-4 w-4" />}>
                <dl className="divide-y divide-line rounded-md border border-line">
                  {g.definitions.map((d) => (
                    <div key={d.term} className="grid gap-1 px-4 py-3 sm:grid-cols-[180px_1fr] sm:gap-4">
                      <dt className="font-semibold text-ink">{d.term}</dt>
                      <dd className="text-sm text-body">
                        <Cited item={{ text: d.definition, location: d.location }} type={type}>
                          {d.definition.charAt(0).toUpperCase() + d.definition.slice(1)}.
                        </Cited>
                      </dd>
                    </div>
                  ))}
                </dl>
              </Section>
            )}
            {points.length > 0 && (
              <Section title={mode === 'concise' ? 'Most important points' : 'Key points'} icon={<Lightbulb className="h-4 w-4" />}>
                <ul className="space-y-2.5">
                  {points.map((p) => (
                    <li key={p.text} className="flex gap-3 text-sm leading-6 text-body">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" aria-hidden />
                      <span>
                        <Cited item={p} type={type} />
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
            {mode === 'detailed' && g.concepts.length > 0 && (
              <Section title="Main concepts" icon={<Sparkles className="h-4 w-4" />}>
                <div className="grid gap-3 sm:grid-cols-2">
                  {g.concepts.map((c) => (
                    <div key={c.term} className="rounded-md border border-line bg-subtle/50 p-3">
                      <p className="text-sm font-semibold text-ink">{c.term}</p>
                      <p className="mt-1 text-sm text-body">
                        <Cited item={c.sentence} type={type} />
                      </p>
                    </div>
                  ))}
                </div>
              </Section>
            )}
            {mode === 'detailed' && g.relationships.length > 0 && (
              <Section title="Relationships between concepts" icon={<Link2 className="h-4 w-4" />}>
                <ul className="space-y-2.5">
                  {g.relationships.map((r) => (
                    <li key={r.text} className="text-sm leading-6 text-body">
                      <Badge className="mr-2">{r.cue}</Badge>
                      <Cited item={r} type={type} />
                    </li>
                  ))}
                </ul>
              </Section>
            )}
            {mode === 'detailed' && g.examples.length > 0 && (
              <Section title="Examples and applications" icon={<Sparkles className="h-4 w-4" />}>
                <ul className="space-y-2.5">
                  {g.examples.map((e) => (
                    <li key={e.text} className="text-sm leading-6 text-body">
                      <Cited item={e} type={type} />
                    </li>
                  ))}
                </ul>
              </Section>
            )}
            {g.revision.length > 0 && (
              <section className="rounded-lg bg-navy p-5 text-white">
                <h3 className="text-[15px] font-semibold text-white">Quick revision</h3>
                <ul className="mt-3 space-y-1.5 text-sm text-brand-100">
                  {g.revision.map((r) => (
                    <li key={r} className="flex gap-2">
                      <span aria-hidden>–</span>
                      {r}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </CardBody>
        </Card>
      )}
      <LLMPanel topicId={topic.id} />
      <div className="flex flex-wrap gap-2">
        <ButtonLink to={`/app/questions?document=${documentId}&topic=${topic.id}`} variant="secondary">
          Questions on this topic
        </ButtonLink>
        <PracticeTopicButton documentId={documentId} topicId={topic.id} disabled={topic.question_count === 0} />
      </div>
    </div>
  );
}

function PracticeTopicButton({ documentId, topicId, disabled }: { documentId: string; topicId: number; disabled: boolean }) {
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();
  const start = async () => {
    setBusy(true);
    try {
      const quiz = await api.createQuiz({ mode: 'topic', document_ids: [documentId], topic_ids: [topicId] });
      navigate(`/app/practice/${quiz.id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not start the quiz.', 'error');
      setBusy(false);
    }
  };
  return (
    <Button onClick={start} loading={busy} disabled={disabled}>
      Practise this topic
    </Button>
  );
}

/** Only rendered when the backend reports a configured local Ollama model. */
function LLMPanel({ topicId }: { topicId: number }) {
  const { llmEnabled } = useServer();
  const [result, setResult] = useState<LLMExplanation>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  if (!llmEnabled) return null;
  const run = async () => {
    setBusy(true);
    setError(undefined);
    try {
      setResult(await api.llmExplanation(topicId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'The local model failed.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ink">Explanation from a local language model</p>
            <p className="text-xs text-muted">Optional. Generated by your configured Ollama model from this topic's passages; check it against the source.</p>
          </div>
          <Button size="sm" variant="secondary" onClick={run} loading={busy}>
            {result ? 'Regenerate' : 'Generate'}
          </Button>
        </div>
        {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        {result && (
          <div className="mt-4 whitespace-pre-line rounded-md border border-line bg-subtle/50 p-4 text-sm text-body">
            <Badge tone="warning" className="mb-2">Generated by {result.model}</Badge>
            <div>{result.text}</div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function SourceView({ topic }: { topic: TopicDetail }) {
  if (!topic.chunks.length) return <EmptyState compact title="No source passages" description="No text was stored for this topic." />;
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">The exact text extracted from your document for this topic, split into retrieval passages.</p>
      {topic.chunks.map((c) => (
        <Card key={c.id}>
          <CardBody>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <SourceRef type={c.location_type} start={c.location_start} end={c.location_end} />
              {c.heading && c.heading !== topic.title && <span className="text-xs font-medium text-muted">{c.heading}</span>}
              <span className="ml-auto text-xs text-muted">{c.word_count} words</span>
            </div>
            <p className="whitespace-pre-line text-sm leading-7 text-body">{c.text}</p>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

const VERDICT = {
  supported: { tone: 'success' as const, label: 'Supported by your notes' },
  partial: { tone: 'warning' as const, label: 'Partial match' },
  insufficient: { tone: 'neutral' as const, label: 'Insufficient evidence' },
};

function AskPanel({ documentId, topic }: { documentId: string; topic: TopicDetail }) {
  const [question, setQuestion] = useState('');
  const [scope, setScope] = useState<'topic' | 'document'>('document');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskResponse>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    setResult(undefined);
  }, [scope]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (question.trim().length < 3) return;
    setBusy(true);
    setError(undefined);
    try {
      setResult(await api.ask(documentId, question.trim(), scope === 'topic' ? topic.id : null));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not answer the question.');
    } finally {
      setBusy(false);
    }
  };

  const suggestions = topic.guide.definitions.slice(0, 2).map((d) => `What is ${d.term}?`);

  return (
    <div className="space-y-5">
      <Card>
        <CardBody>
          <form onSubmit={submit} className="space-y-3">
            <label htmlFor="ask" className="label">
              Ask a question about your material
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                id="ask"
                className="field"
                placeholder="e.g. Why can accuracy be misleading?"
                value={question}
                maxLength={500}
                onChange={(e) => setQuestion(e.target.value)}
              />
              <Button type="submit" loading={busy} disabled={question.trim().length < 3} icon={<Send className="h-4 w-4" />}>
                Ask
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Segmented
                size="sm"
                label="Search scope"
                value={scope}
                onChange={setScope}
                options={[
                  { value: 'document', label: 'Whole document' },
                  { value: 'topic', label: 'This topic' },
                ]}
              />
              {suggestions.map((s) => (
                <button key={s} type="button" onClick={() => setQuestion(s)} className="text-xs font-medium text-brand-700 hover:underline">
                  {s}
                </button>
              ))}
            </div>
          </form>
          <p className="mt-3 text-xs text-muted">
            Answers are sentences retrieved from your document with TF-IDF and cosine similarity. A high score means shared
            vocabulary, not proof that the passage answers the question.
          </p>
        </CardBody>
      </Card>
      {busy && <Spinner label="Searching your notes…" />}
      {error && <Alert tone="danger">{error}</Alert>}
      {result && !busy && (
        <div className="space-y-4" aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={VERDICT[result.verdict].tone}>{VERDICT[result.verdict].label}</Badge>
            <span className="text-xs text-muted">
              Top similarity {result.top_score.toFixed(2)} · query terms covered {Math.round(result.coverage * 100)}%
            </span>
          </div>
          <p className="text-sm text-body">{result.message}</p>
          {result.answer.length > 0 && (
            <Card>
              <CardBody className="space-y-3">
                <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <MessageSquareText className="h-4 w-4 text-brand-600" /> Answer from your notes
                </p>
                {result.answer.map((a) => (
                  <blockquote key={a.text} className="border-l-2 border-brand-300 pl-3 text-[15px] leading-7 text-body">
                    {a.text} <SourceRef type={a.location_type} start={a.location} className="align-middle" />
                  </blockquote>
                ))}
              </CardBody>
            </Card>
          )}
          {result.passages.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Retrieved passages</p>
              <div className="space-y-2">
                {result.passages.map((p) => (
                  <details key={p.chunk_id} className="rounded-md border border-line bg-surface px-4 py-3 text-sm">
                    <summary className="flex cursor-pointer items-center gap-2">
                      <SourceRef type={p.location_type} start={p.location_start} end={p.location_end} />
                      <span className="truncate font-medium text-ink">{p.heading}</span>
                      <span className="ml-auto text-xs text-muted">score {p.score.toFixed(2)}</span>
                    </summary>
                    <p className="mt-2 whitespace-pre-line text-body">{p.text}</p>
                  </details>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
