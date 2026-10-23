import type { ReactElement } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ToastProvider } from '../components/ui/Toast';
import type { DocumentSummary, Quiz, QuizResult, TopicDetail, TopicSummary } from '../types/api';

export function renderAt(ui: ReactElement, { path = '/', route = '/' }: { path?: string; route?: string } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ToastProvider>
        <Routes>
          <Route path={path} element={ui} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

export const doc = (overrides: Partial<DocumentSummary> = {}): DocumentSummary => ({
  id: 'd1',
  name: 'Foundations of NLP',
  original_filename: 'nlp.pdf',
  file_type: 'pdf',
  size_bytes: 120_000,
  status: 'ready',
  error_code: null,
  error_message: null,
  is_sample: false,
  unit_label: 'page',
  unit_count: 3,
  word_count: 935,
  chunk_count: 9,
  topic_count: 2,
  question_count: 40,
  created_at: '2026-10-20T10:00:00Z',
  updated_at: '2026-10-20T10:00:00Z',
  ...overrides,
});

export const topics: TopicSummary[] = [
  { id: 11, document_id: 'd1', position: 0, title: 'Tokenization', title_source: 'heading', keywords: ['tokens'], location_type: 'page', location_start: 1, location_end: 1, word_count: 90, question_count: 8 },
  { id: 12, document_id: 'd1', position: 1, title: 'Word Embeddings', title_source: 'heading', keywords: ['Word2Vec'], location_type: 'page', location_start: 2, location_end: 2, word_count: 80, question_count: 6 },
];

export const topicDetail = (t: TopicSummary): TopicDetail => ({
  ...t,
  document_name: 'Foundations of NLP',
  unit_label: 'page',
  guide: {
    method: 'extractive-rule-based',
    overview: [{ text: `${t.title} overview sentence from the notes.`, location: t.location_start }],
    definitions: [{ term: t.title, definition: `the definition of ${t.title}`, text: '', location: t.location_start }],
    key_points: [{ text: `A key point about ${t.title}.`, location: t.location_start, rank: 0 }],
    concepts: [],
    relationships: [],
    examples: [],
    revision: [`${t.title}: revision line`],
    locations: [t.location_start],
    sentence_count: 5,
  },
  chunks: [{ id: 100 + t.id, position: 0, topic_id: t.id, heading: t.title, text: `Source text for ${t.title}.`, location_type: 'page', location_start: 1, location_end: 1, word_count: 4 }],
  prev_topic_id: t.position === 0 ? null : 11,
  next_topic_id: t.position === 0 ? 12 : null,
});

export const quiz: Quiz = {
  id: 'q1',
  title: 'Mid-semester practice',
  mode: 'mid_sem',
  status: 'in_progress',
  time_limit_minutes: null,
  created_at: new Date().toISOString(),
  total: 2,
  document_ids: ['d1'],
  questions: [
    { question_id: 'a', position: 0, stem: 'Which term matches splitting text into tokens?', options: ['Tokenization', 'Stemming', 'Parsing', 'Tagging'], topic_id: 11, topic_title: 'Tokenization', difficulty: 'easy', category: 'definition', selected_index: null, marked_for_review: false },
    { question_id: 'b', position: 1, stem: 'Fill in the blank: _____ learns embeddings.', options: ['BLEU', 'Word2Vec', 'TF-IDF', 'Recall'], topic_id: 12, topic_title: 'Word Embeddings', difficulty: 'medium', category: 'factual', selected_index: null, marked_for_review: false },
  ],
};

export const result: QuizResult = {
  id: 'q1',
  title: 'Mid-semester practice',
  mode: 'mid_sem',
  status: 'submitted',
  total: 2,
  correct_count: 1,
  incorrect_count: 1,
  unanswered_count: 0,
  answered_count: 2,
  score_percent: 50,
  duration_seconds: 75,
  time_limit_minutes: null,
  created_at: '2026-10-20T10:00:00Z',
  submitted_at: '2026-10-20T10:01:15Z',
  topic_breakdown: [
    { topic_id: 11, topic_title: 'Tokenization', correct: 1, total: 1 },
    { topic_id: 12, topic_title: 'Word Embeddings', correct: 0, total: 1 },
  ],
  items: [
    { question_id: 'a', position: 0, stem: 'Which term matches splitting text into tokens?', options: ['Tokenization', 'Stemming', 'Parsing', 'Tagging'], selected_index: 0, correct_index: 0, status: 'correct', explanation: 'Your notes define tokenization…', option_notes: null, evidence: 'Tokenization is…', location_type: 'page', location_start: 1, location_end: 1, topic_id: 11, topic_title: 'Tokenization', document_id: 'd1', difficulty: 'easy', category: 'definition', marked_for_review: false },
    { question_id: 'b', position: 1, stem: 'Fill in the blank: _____ learns embeddings.', options: ['BLEU', 'Word2Vec', 'TF-IDF', 'Recall'], selected_index: 0, correct_index: 1, status: 'incorrect', explanation: 'The original statement reads…', option_notes: ['BLEU is a different concept: a translation metric.', null, null, null], evidence: 'Word2Vec learns…', location_type: 'page', location_start: 2, location_end: 2, topic_id: 12, topic_title: 'Word Embeddings', document_id: 'd1', difficulty: 'medium', category: 'factual', marked_for_review: true },
  ],
};
