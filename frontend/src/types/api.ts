// Mirrors backend/app/schemas. Keep in sync when the API changes.

export type Difficulty = 'easy' | 'medium' | 'hard';
export type QuestionType = 'mcq' | 'short_answer' | 'long_answer';
export type Category = 'definition' | 'factual' | 'conceptual' | 'application' | 'revision';
export type QuizMode = 'mid_sem' | 'end_sem' | 'topic' | 'custom' | 'retry';
export type DocumentStatus = 'processing' | 'ready' | 'failed';

export interface Health {
  status: 'ok' | 'degraded';
  version: string;
  environment: string;
  database: 'ok' | 'error';
  database_backend: string;
  llm_enabled: boolean;
  max_upload_mb: number;
}

export interface WorkspaceInfo {
  workspace_id: string;
  created_at: string;
  document_count: number;
  attempt_count: number;
  max_documents: number;
  max_upload_mb: number;
  llm_enabled: boolean;
}

export interface Chunk {
  id: number;
  position: number;
  topic_id: number | null;
  heading: string | null;
  text: string;
  location_type: string;
  location_start: number;
  location_end: number;
  word_count: number;
}

export interface TopicSummary {
  id: number;
  document_id: string;
  position: number;
  title: string;
  title_source: 'heading' | 'keywords' | 'default';
  keywords: string[];
  location_type: string;
  location_start: number;
  location_end: number;
  word_count: number;
  question_count: number;
}

export interface DocumentSummary {
  id: string;
  name: string;
  original_filename: string;
  file_type: 'pdf' | 'docx' | 'pptx';
  size_bytes: number;
  status: DocumentStatus;
  error_code: string | null;
  error_message: string | null;
  is_sample: boolean;
  unit_label: string;
  unit_count: number;
  word_count: number;
  chunk_count: number;
  topic_count: number;
  question_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentStats {
  definitions?: number;
  sentences?: number;
  keyphrases?: number;
  questions_by_type?: Partial<Record<QuestionType, number>>;
  rejected_total?: number;
  rejected_reasons?: Record<string, number>;
}

export interface DocumentDetail extends DocumentSummary {
  warnings: string[];
  stats: DocumentStats;
  segmentation_method: string | null;
  heading_count: number;
  rejected_question_count: number;
  processing_ms: number;
  topics: TopicSummary[];
  preview: Chunk[];
  duplicate: boolean;
}

export interface DeleteImpact {
  document_id: string;
  topics: number;
  questions: number;
  quiz_attempts: number;
}

export interface ContentPage {
  items: Chunk[];
  total: number;
  offset: number;
  limit: number;
}

export interface GuideItem {
  text: string;
  location: number;
  rank?: number;
  cue?: string;
}

export interface GuideDefinition {
  term: string;
  definition: string;
  text: string;
  location: number;
}

export interface Guide {
  method: string;
  overview: GuideItem[];
  definitions: GuideDefinition[];
  key_points: GuideItem[];
  concepts: { term: string; sentence: GuideItem }[];
  relationships: GuideItem[];
  examples: GuideItem[];
  revision: string[];
  locations: number[];
  sentence_count: number;
}

export interface TopicDetail extends TopicSummary {
  document_name: string;
  unit_label: string;
  guide: Guide;
  chunks: Chunk[];
  prev_topic_id: number | null;
  next_topic_id: number | null;
}

export interface AnswerSentence {
  text: string;
  location_type: string;
  location: number;
  topic_id: number | null;
  score?: number | null;
}

export interface Passage {
  chunk_id: number;
  text: string;
  heading: string | null;
  topic_id: number | null;
  location_type: string;
  location_start: number;
  location_end: number;
  score: number;
}

export interface AskResponse {
  question: string;
  verdict: 'supported' | 'partial' | 'insufficient';
  message: string;
  answer: AnswerSentence[];
  passages: Passage[];
  coverage: number;
  top_score: number;
  method: string;
}

export interface LLMExplanation {
  topic_id: number;
  model: string;
  text: string;
  passages_used: number;
}

export interface Question {
  id: string;
  document_id: string;
  topic_id: number | null;
  topic_title: string | null;
  question_type: QuestionType;
  category: Category;
  difficulty: Difficulty;
  stem: string;
  options: string[] | null;
  correct_index: number | null;
  option_notes: (string | null)[] | null;
  answer_text: string;
  explanation: string;
  evidence: string;
  location_type: string;
  location_start: number;
  location_end: number;
}

export interface QuestionBankPage {
  items: Question[];
  total: number;
  offset: number;
  limit: number;
  counts: Record<'question_type' | 'difficulty' | 'category', Record<string, number>>;
}

export interface QuestionSetRequest {
  document_id: string;
  topic_ids?: number[];
  difficulties?: Difficulty[];
  question_types?: QuestionType[];
  categories?: Category[];
  count: number;
  seed?: number;
}

export interface QuestionSetResponse {
  questions: Question[];
  requested: number;
  available: number;
  message: string;
}

export interface QuizCreate {
  mode: QuizMode;
  document_ids?: string[];
  topic_ids?: number[];
  difficulties?: Difficulty[];
  count?: number;
  time_limit_minutes?: number | null;
  source_attempt_id?: string;
  title?: string;
}

export interface QuizQuestion {
  question_id: string;
  position: number;
  stem: string;
  options: string[];
  topic_id: number | null;
  topic_title: string | null;
  difficulty: Difficulty;
  category: Category;
  selected_index: number | null;
  marked_for_review: boolean;
}

export interface Quiz {
  id: string;
  title: string;
  mode: QuizMode;
  status: 'in_progress' | 'submitted';
  time_limit_minutes: number | null;
  created_at: string;
  total: number;
  document_ids: string[];
  questions: QuizQuestion[];
}

export interface ResponseIn {
  question_id: string;
  selected_index: number | null;
  marked_for_review: boolean;
}

export interface QuizResultItem {
  question_id: string;
  position: number;
  stem: string;
  options: string[];
  selected_index: number | null;
  correct_index: number;
  status: 'correct' | 'incorrect' | 'unanswered';
  explanation: string;
  option_notes: (string | null)[] | null;
  evidence: string;
  location_type: string;
  location_start: number;
  location_end: number;
  topic_id: number | null;
  topic_title: string | null;
  document_id: string;
  difficulty: Difficulty;
  category: Category;
  marked_for_review: boolean;
}

export interface TopicScore {
  topic_id: number | null;
  topic_title: string;
  correct: number;
  total: number;
}

export interface QuizResult {
  id: string;
  title: string;
  mode: QuizMode;
  status: string;
  total: number;
  correct_count: number;
  incorrect_count: number;
  unanswered_count: number;
  answered_count: number;
  score_percent: number;
  duration_seconds: number | null;
  time_limit_minutes: number | null;
  created_at: string;
  submitted_at: string | null;
  items: QuizResultItem[];
  topic_breakdown: TopicScore[];
}

export interface QuizHistoryItem {
  id: string;
  title: string;
  mode: QuizMode;
  status: 'in_progress' | 'submitted';
  total: number;
  correct_count: number;
  answered_count: number;
  score_percent: number | null;
  created_at: string;
  submitted_at: string | null;
  duration_seconds: number | null;
  document_ids: string[];
}

export type TopicStatus = 'not_started' | 'insufficient' | 'weak' | 'developing' | 'strong';

export interface TopicProgress {
  topic_id: number;
  topic_title: string;
  document_id: string;
  document_name: string;
  attempted: number;
  correct: number;
  accuracy: number | null;
  status: TopicStatus;
  last_practiced: string | null;
}

export interface Recommendation {
  kind: 'revise' | 'practice' | 'start' | 'retry' | 'maintain' | 'upload';
  title: string;
  detail: string;
  topic_id: number | null;
  document_id: string | null;
  attempt_id: string | null;
}

export interface ActivityItem {
  kind: 'upload' | 'quiz';
  title: string;
  detail: string;
  at: string;
  ref_id: string;
}

export interface ProgressSummary {
  documents_ready: number;
  documents_total: number;
  attempts_submitted: number;
  attempts_in_progress: number;
  questions_answered: number;
  questions_correct: number;
  average_accuracy: number | null;
  min_answers_for_accuracy: number;
  min_answers_per_topic: number;
  topics: TopicProgress[];
  weak_topics: TopicProgress[];
  insufficient_topics: TopicProgress[];
  recommendations: Recommendation[];
  recent_activity: ActivityItem[];
  accuracy_trend: { attempt_id: string; title: string; score_percent: number; submitted_at: string }[];
}

export interface IncorrectItem {
  question_id: string;
  attempt_id: string;
  attempt_title: string;
  answered_at: string | null;
  stem: string;
  options: string[];
  selected_index: number | null;
  correct_index: number;
  explanation: string;
  evidence: string;
  location_type: string;
  location_start: number;
  topic_id: number | null;
  topic_title: string | null;
  document_id: string;
  times_missed: number;
}
