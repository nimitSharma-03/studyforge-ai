import { Link } from 'react-router-dom';
import { AlertTriangle, BookOpenText, ClipboardCheck, ListChecks } from 'lucide-react';
import type { DocumentDetail } from '../types/api';
import { Card, CardBody, CardHeader } from './ui/Card';
import { Badge, SourceRef } from './ui/Badge';
import { ButtonLink } from './ui/Button';
import { Alert } from './ui/Feedback';
import { pluralize } from '../utils/format';

const SEGMENTATION: Record<string, string> = {
  headings: 'document headings',
  slides: 'slide titles',
  single: 'a single topic (no headings found)',
  texttiling: 'lexical cohesion (TextTiling), since no headings were found',
  'headings+texttiling': 'headings, with long sections split by lexical cohesion',
  'slides+texttiling': 'slide titles, with long sections split by lexical cohesion',
};

const REASONS: Record<string, string> = {
  insufficient_distractors: 'not enough distinct answer options',
  duplicate: 'duplicate',
  near_duplicate: 'near-duplicate wording',
  pronoun_reference: 'sentence depends on earlier context',
  sentence_length: 'sentence too short or long',
  low_context: 'too little context left after blanking',
  length_imbalance: 'options of very uneven length',
  option_in_stem: 'an option appears in the question',
  answer_not_in_source: 'answer not found in the source',
  distractor_in_source_statement: 'a wrong option appears in the source statement',
};

/** Extraction and analysis summary for a processed document. All numbers come from the API. */
export function DocumentOverview({ doc }: { doc: DocumentDetail }) {
  if (doc.status === 'failed') {
    return (
      <Alert tone="danger" title="This document could not be processed">
        <p>{doc.error_message ?? 'An unknown error occurred.'}</p>
        {doc.error_code === 'scanned_pdf' && (
          <p className="mt-2">
            Tip: open the PDF in a tool with OCR (for example, “Make searchable” in many PDF readers), save it, and upload the new file.
          </p>
        )}
      </Alert>
    );
  }
  const byType = doc.stats.questions_by_type ?? {};
  const reasons = Object.entries(doc.stats.rejected_reasons ?? {}).filter(([k]) => !k.endsWith('_skipped'));
  return (
    <div className="space-y-6">
      {doc.warnings.length > 0 && (
        <Alert tone="warning" title="Processed with warnings">
          <ul className="list-disc pl-4">
            {doc.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          [pluralize(doc.unit_count, doc.unit_label), `${doc.word_count.toLocaleString()} words extracted`],
          [pluralize(doc.topic_count, 'topic'), `Segmented using ${SEGMENTATION[doc.segmentation_method ?? 'single'] ?? doc.segmentation_method}`],
          [pluralize(doc.chunk_count, 'passage'), 'Source-aware chunks indexed with TF-IDF'],
          [pluralize(doc.question_count, 'question'), `${byType.mcq ?? 0} MCQ · ${byType.short_answer ?? 0} short · ${byType.long_answer ?? 0} long`],
        ].map(([value, hint]) => (
          <div key={value} className="rounded-lg border border-line bg-surface p-4">
            <p className="text-lg font-semibold text-ink">{value}</p>
            <p className="mt-0.5 text-xs text-muted">{hint}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <ButtonLink to={`/app/learn/${doc.id}`} icon={<BookOpenText className="h-4 w-4" />}>
          Start learning
        </ButtonLink>
        <ButtonLink to={`/app/questions?document=${doc.id}`} variant="secondary" icon={<ListChecks className="h-4 w-4" />}>
          Question bank
        </ButtonLink>
        <ButtonLink to={`/app/practice?document=${doc.id}`} variant="secondary" icon={<ClipboardCheck className="h-4 w-4" />}>
          Practice test
        </ButtonLink>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="Topics found" description={`${doc.heading_count} headings detected in the document.`} />
          <ol className="divide-y divide-line">
            {doc.topics.map((t) => (
              <li key={t.id} className="flex items-start gap-3 px-5 py-3">
                <span className="mt-0.5 w-6 shrink-0 text-sm tabular-nums text-muted">{t.position + 1}.</span>
                <div className="min-w-0 flex-1">
                  <Link to={`/app/learn/${doc.id}/${t.id}`} className="font-medium text-ink hover:text-brand-700">
                    {t.title}
                  </Link>
                  {t.title_source === 'keywords' && <span className="ml-2 text-xs text-muted">(title from keyphrases)</span>}
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <SourceRef type={t.location_type} start={t.location_start} end={t.location_end} />
                    {t.keywords.slice(0, 4).map((k) => (
                      <Badge key={k}>{k}</Badge>
                    ))}
                  </div>
                </div>
                <span className="shrink-0 text-xs text-muted">{pluralize(t.question_count, 'question')}</span>
              </li>
            ))}
          </ol>
        </Card>
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Extracted text preview" description="The first passages, exactly as extracted." />
            <CardBody className="space-y-4">
              {doc.preview.map((c) => (
                <div key={c.id}>
                  <div className="mb-1 flex items-center gap-2">
                    <SourceRef type={c.location_type} start={c.location_start} end={c.location_end} />
                    {c.heading && <span className="truncate text-xs font-medium text-muted">{c.heading}</span>}
                  </div>
                  <p className="line-clamp-5 whitespace-pre-line text-sm text-body">{c.text}</p>
                </div>
              ))}
              <Link to={`/app/learn/${doc.id}?tab=source`} className="inline-block text-sm font-medium text-brand-700 hover:underline">
                Read all extracted content
              </Link>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Question quality checks" />
            <CardBody className="text-sm">
              <p className="text-body">
                {doc.question_count} questions passed validation; {doc.rejected_question_count} candidates were rejected
                {reasons.length ? ':' : '.'}
              </p>
              {reasons.length > 0 && (
                <ul className="mt-2 space-y-1 text-muted">
                  {reasons.map(([k, v]) => (
                    <li key={k} className="flex justify-between gap-3">
                      <span className="flex items-center gap-1.5">
                        <AlertTriangle className="h-3.5 w-3.5 text-warning" aria-hidden />
                        {REASONS[k] ?? k.replace(/_/g, ' ')}
                      </span>
                      <span className="tabular-nums">{v}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-muted">
                {doc.stats.definitions ?? 0} definitions and {doc.stats.keyphrases ?? 0} keyphrases were detected across{' '}
                {doc.stats.sentences ?? 0} sentences. Processing took {(doc.processing_ms / 1000).toFixed(1)} s.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
