import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Download, Search, Shuffle, SlidersHorizontal } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { NoDocuments } from '../components/NoDocuments';
import { QuestionCard } from '../components/QuestionCard';
import { Card, CardBody } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ChipGroup, Select, Tabs, Toggle } from '../components/ui/Controls';
import { EmptyState } from '../components/ui/EmptyState';
import { Alert, ErrorState, PageLoader, Spinner } from '../components/ui/Feedback';
import { useToast } from '../components/ui/Toast';
import { useApi } from '../hooks/useApi';
import { api, ApiError, type ExportFormat } from '../services/api';
import type { Category, Difficulty, QuestionSetResponse, QuestionType } from '../types/api';
import { CATEGORY_LABEL, DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from '../utils/format';

const TYPES = (Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => ({ value, label: QUESTION_TYPE_LABEL[value] }));
const DIFFS = (Object.keys(DIFFICULTY_LABEL) as Difficulty[]).map((value) => ({ value, label: DIFFICULTY_LABEL[value] }));
const CATS = (Object.keys(CATEGORY_LABEL) as Category[]).map((value) => ({ value, label: CATEGORY_LABEL[value] }));
const PAGE = 20;

export default function QuestionBank() {
  const docs = useApi(() => api.documents(), []);
  const [params, setParams] = useSearchParams();
  if (docs.loading) return <PageLoader />;
  if (docs.error) return <ErrorState error={docs.error} onRetry={docs.reload} />;
  const ready = (docs.data ?? []).filter((d) => d.status === 'ready');
  const header = (
    <PageHeader
      title="Question Bank"
      description="Questions generated from your material when it was processed, each checked by automatic validation rules."
    />
  );
  if (!ready.length) return (<>{header}<NoDocuments purpose="questions" /></>);
  const docId = ready.some((d) => d.id === params.get('document')) ? params.get('document')! : ready[0].id;
  const initialTopic = Number(params.get('topic')) || undefined;
  return (
    <>
      {header}
      <div className="mb-5 max-w-sm">
        <label htmlFor="qb-doc" className="label">
          Document
        </label>
        <Select id="qb-doc" value={docId} onChange={(e) => setParams({ document: e.target.value })}>
          {ready.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.question_count})
            </option>
          ))}
        </Select>
      </div>
      <BankForDocument key={docId} documentId={docId} initialTopic={initialTopic} />
    </>
  );
}

function BankForDocument({ documentId, initialTopic }: { documentId: string; initialTopic?: number }) {
  const topics = useApi(() => api.topics(documentId), [documentId]);
  const [topicIds, setTopicIds] = useState<string[]>(initialTopic ? [String(initialTopic)] : []);
  const [types, setTypes] = useState<QuestionType[]>([]);
  const [difficulties, setDifficulties] = useState<Difficulty[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [view, setView] = useState<'browse' | 'generate'>('browse');
  const [revealAll, setRevealAll] = useState(false);
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [offset, setOffset] = useState(0);
  const [count, setCount] = useState(10);
  const [set, setSet] = useState<QuestionSetResponse>();
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);
  const filterKey = JSON.stringify([topicIds, types, difficulties, categories, debounced]);
  useEffect(() => setOffset(0), [filterKey]);

  const filters = useMemo(
    () => ({ topic_id: topicIds.map(Number), question_type: types, difficulty: difficulties, category: categories }),
    [topicIds, types, difficulties, categories],
  );
  const bank = useApi(
    () => api.questionBank({ document_id: documentId, ...filters, search: debounced || undefined, offset, limit: PAGE }),
    [documentId, filterKey, offset],
    view === 'browse',
  );

  const generate = async () => {
    setGenerating(true);
    try {
      setSet(
        await api.generateQuestionSet({
          document_id: documentId,
          topic_ids: filters.topic_id,
          question_types: types,
          difficulties,
          categories,
          count,
          seed: Math.floor(Math.random() * 1e9),
        }),
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not build the question set.', 'error');
    } finally {
      setGenerating(false);
    }
  };

  const exportBank = async (format: ExportFormat, answers: boolean) => {
    const key = `${format}-${answers}`;
    setExporting(key);
    try {
      await api.exportQuestions(documentId, format, { answers, ...filters });
    } catch (err) {
      toast(err instanceof ApiError ? `Export failed: ${err.message}` : 'Export failed.', 'error');
    } finally {
      setExporting(null);
    }
  };

  if (topics.loading) return <PageLoader />;
  if (topics.error) return <ErrorState error={topics.error} onRetry={topics.reload} />;
  const topicOptions = (topics.data ?? []).map((t) => ({ value: String(t.id), label: t.title }));
  const counts = bank.data?.counts;

  return (
    <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
      <aside className="space-y-4">
        <Card>
          <CardBody className="space-y-5">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <SlidersHorizontal className="h-4 w-4 text-brand-600" /> Filters
            </p>
            <ChipGroup label="Question type" options={TYPES} value={types} onChange={setTypes} counts={counts?.question_type} />
            <ChipGroup label="Difficulty" options={DIFFS} value={difficulties} onChange={setDifficulties} counts={counts?.difficulty} />
            <ChipGroup label="Category" options={CATS} value={categories} onChange={setCategories} counts={counts?.category} />
            <div>
              <label htmlFor="qb-topic" className="label">
                Topics
              </label>
              <select
                id="qb-topic"
                multiple
                className="field h-40"
                value={topicIds}
                onChange={(e) => setTopicIds(Array.from(e.target.selectedOptions, (o) => o.value))}
              >
                {topicOptions.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted">
                {topicIds.length ? `${topicIds.length} selected · ` : 'All topics · '}
                Ctrl/⌘-click to select several.{' '}
                {topicIds.length > 0 && (
                  <button type="button" className="font-medium text-brand-700 hover:underline" onClick={() => setTopicIds([])}>
                    Clear
                  </button>
                )}
              </p>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="space-y-3">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Download className="h-4 w-4 text-brand-600" /> Download (current filters)
            </p>
            <div className="grid grid-cols-3 gap-2">
              {(['md', 'txt', 'pdf'] as const).map((f) => (
                <Button key={f} size="sm" variant="secondary" loading={exporting === `${f}-true`} onClick={() => exportBank(f, true)}>
                  {f.toUpperCase()}
                </Button>
              ))}
            </div>
            <p className="text-xs text-muted">Includes an answer key with explanations and sources.</p>
            <button
              type="button"
              className="text-xs font-medium text-brand-700 hover:underline disabled:opacity-50"
              disabled={!!exporting}
              onClick={() => exportBank('pdf', false)}
            >
              {exporting === 'pdf-false' ? 'Preparing…' : 'Download questions only (PDF, no answers)'}
            </button>
          </CardBody>
        </Card>
      </aside>

      <section className="min-w-0">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <Tabs
            label="Question bank view"
            value={view}
            onChange={setView}
            tabs={[
              { value: 'browse', label: 'Browse bank' },
              { value: 'generate', label: 'Generate question set' },
            ]}
          />
          <Toggle checked={revealAll} onChange={setRevealAll} label="Show all answers" />
        </div>

        {view === 'browse' ? (
          <div className="mt-5 space-y-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
              <input className="field pl-9" placeholder="Search question text" aria-label="Search questions" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            {bank.loading ? (
              <Spinner label="Loading questions…" />
            ) : bank.error ? (
              <ErrorState error={bank.error} onRetry={bank.reload} />
            ) : bank.data!.items.length === 0 ? (
              <EmptyState
                compact
                icon={<Search className="h-5 w-5" />}
                title="No questions match these filters"
                description="Try removing a filter. Only questions that passed the quality checks are stored."
              />
            ) : (
              <>
                <p className="text-sm text-muted">
                  Showing {offset + 1}–{offset + bank.data!.items.length} of {bank.data!.total}
                </p>
                {bank.data!.items.map((q, i) => (
                  <QuestionCard key={q.id} q={q} index={offset + i + 1} revealAll={revealAll} />
                ))}
                <div className="flex justify-between">
                  <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                    Previous
                  </Button>
                  <Button variant="secondary" disabled={offset + PAGE >= bank.data!.total} onClick={() => setOffset(offset + PAGE)}>
                    Next
                  </Button>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            <Card>
              <CardBody className="flex flex-wrap items-end gap-4">
                <div className="w-32">
                  <label htmlFor="qb-count" className="label">
                    Questions
                  </label>
                  <input
                    id="qb-count"
                    type="number"
                    min={1}
                    max={100}
                    className="field"
                    value={count}
                    onChange={(e) => setCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
                  />
                </div>
                <Button onClick={generate} loading={generating} icon={<Shuffle className="h-4 w-4" />}>
                  Generate question set
                </Button>
                <p className="w-full text-xs text-muted">
                  Draws a random set from the validated questions matching your filters. Sets are never padded with questions that
                  failed the quality checks.
                </p>
              </CardBody>
            </Card>
            {set && (
              <>
                <Alert tone={set.available >= set.requested ? 'success' : set.available ? 'warning' : 'info'}>{set.message}</Alert>
                {set.questions.map((q, i) => (
                  <QuestionCard key={q.id} q={q} index={i + 1} revealAll={revealAll} />
                ))}
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
