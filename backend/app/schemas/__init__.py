"""Pydantic request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["easy", "medium", "hard"]
QuestionType = Literal["mcq", "short_answer", "long_answer"]
Category = Literal["definition", "factual", "conceptual", "application", "revision"]
QuizMode = Literal["mid_sem", "end_sem", "topic", "custom", "retry"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- system


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "error"]
    database_backend: str
    llm_enabled: bool
    max_upload_mb: int


class WorkspaceCreated(BaseModel):
    token: str
    workspace_id: str
    created_at: datetime


class WorkspaceInfo(BaseModel):
    workspace_id: str
    created_at: datetime
    document_count: int
    attempt_count: int
    max_documents: int
    max_upload_mb: int
    llm_enabled: bool


# ---------------------------------------------------------------- documents


class ChunkOut(ORM):
    id: int
    position: int
    topic_id: int | None
    heading: str | None
    text: str
    location_type: str
    location_start: int
    location_end: int
    word_count: int


class TopicSummary(ORM):
    id: int
    document_id: str
    position: int
    title: str
    title_source: str
    keywords: list[str]
    location_type: str
    location_start: int
    location_end: int
    word_count: int
    question_count: int = 0


class DocumentSummary(ORM):
    id: str
    name: str
    original_filename: str
    file_type: str
    size_bytes: int
    status: str
    error_code: str | None
    error_message: str | None
    is_sample: bool
    unit_label: str
    unit_count: int
    word_count: int
    chunk_count: int
    topic_count: int
    question_count: int
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentSummary):
    warnings: list[str]
    stats: dict
    segmentation_method: str | None
    heading_count: int
    rejected_question_count: int
    processing_ms: int
    topics: list[TopicSummary] = []
    preview: list[ChunkOut] = []
    duplicate: bool = False


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class DeleteImpact(BaseModel):
    document_id: str
    topics: int
    questions: int
    quiz_attempts: int


class ContentPage(BaseModel):
    items: list[ChunkOut]
    total: int
    offset: int
    limit: int


class TopicDetail(TopicSummary):
    document_name: str
    unit_label: str
    guide: dict
    chunks: list[ChunkOut]
    prev_topic_id: int | None
    next_topic_id: int | None


# ---------------------------------------------------------------- retrieval


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    topic_id: int | None = None


class AnswerSentence(BaseModel):
    text: str
    location_type: str
    location: int
    topic_id: int | None = None
    score: float | None = None


class PassageOut(BaseModel):
    chunk_id: int
    text: str
    heading: str | None
    topic_id: int | None
    location_type: str
    location_start: int
    location_end: int
    score: float


class AskResponse(BaseModel):
    question: str
    verdict: Literal["supported", "partial", "insufficient"]
    message: str
    answer: list[AnswerSentence]
    passages: list[PassageOut]
    coverage: float
    top_score: float
    method: str = "tfidf-extractive"


class LLMExplanation(BaseModel):
    topic_id: int
    model: str
    text: str
    passages_used: int


# ---------------------------------------------------------------- questions


class QuestionOut(ORM):
    id: str
    document_id: str
    topic_id: int | None
    topic_title: str | None = None
    question_type: str
    category: str
    difficulty: str
    stem: str
    options: list[str] | None
    correct_index: int | None
    option_notes: list[str | None] | None
    answer_text: str
    explanation: str
    evidence: str
    location_type: str
    location_start: int
    location_end: int


class QuestionBankPage(BaseModel):
    items: list[QuestionOut]
    total: int
    offset: int
    limit: int
    counts: dict[str, dict[str, int]]


class QuestionSetRequest(BaseModel):
    document_id: str
    topic_ids: list[int] = []
    difficulties: list[Difficulty] = []
    question_types: list[QuestionType] = []
    categories: list[Category] = []
    count: int = Field(default=10, ge=1, le=100)
    seed: int | None = None


class QuestionSetResponse(BaseModel):
    questions: list[QuestionOut]
    requested: int
    available: int
    message: str


# ---------------------------------------------------------------- quizzes


class QuizCreate(BaseModel):
    mode: QuizMode
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    topic_ids: list[int] = Field(default_factory=list, max_length=100)
    difficulties: list[Difficulty] = []
    count: int | None = Field(default=None, ge=1, le=100)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=240)
    source_attempt_id: str | None = None
    title: str | None = Field(default=None, max_length=120)


class QuizQuestionOut(BaseModel):
    question_id: str
    position: int
    stem: str
    options: list[str]
    topic_id: int | None
    topic_title: str | None
    difficulty: str
    category: str
    selected_index: int | None
    marked_for_review: bool


class QuizOut(BaseModel):
    id: str
    title: str
    mode: str
    status: str
    time_limit_minutes: int | None
    created_at: datetime
    total: int
    document_ids: list[str]
    questions: list[QuizQuestionOut]


class ResponseIn(BaseModel):
    question_id: str
    selected_index: int | None = Field(default=None, ge=0, le=3)
    marked_for_review: bool = False


class SaveResponses(BaseModel):
    responses: list[ResponseIn] = Field(max_length=100)


class SubmitRequest(BaseModel):
    responses: list[ResponseIn] = Field(default_factory=list, max_length=100)
    duration_seconds: int | None = Field(default=None, ge=0, le=60 * 60 * 6)


class QuizResultItem(BaseModel):
    question_id: str
    position: int
    stem: str
    options: list[str]
    selected_index: int | None
    correct_index: int
    status: Literal["correct", "incorrect", "unanswered"]
    explanation: str
    option_notes: list[str | None] | None
    evidence: str
    location_type: str
    location_start: int
    location_end: int
    topic_id: int | None
    topic_title: str | None
    document_id: str
    difficulty: str
    category: str
    marked_for_review: bool


class TopicScore(BaseModel):
    topic_id: int | None
    topic_title: str
    correct: int
    total: int


class QuizResult(BaseModel):
    id: str
    title: str
    mode: str
    status: str
    total: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    answered_count: int
    score_percent: float
    duration_seconds: int | None
    time_limit_minutes: int | None
    created_at: datetime
    submitted_at: datetime | None
    items: list[QuizResultItem]
    topic_breakdown: list[TopicScore]


class QuizHistoryItem(BaseModel):
    id: str
    title: str
    mode: str
    status: str
    total: int
    correct_count: int
    answered_count: int
    score_percent: float | None
    created_at: datetime
    submitted_at: datetime | None
    duration_seconds: int | None
    document_ids: list[str]


# ---------------------------------------------------------------- progress


class TopicProgress(BaseModel):
    topic_id: int
    topic_title: str
    document_id: str
    document_name: str
    attempted: int
    correct: int
    accuracy: float | None
    status: Literal["not_started", "insufficient", "weak", "developing", "strong"]
    last_practiced: datetime | None


class Recommendation(BaseModel):
    kind: Literal["revise", "practice", "start", "retry", "maintain", "upload"]
    title: str
    detail: str
    topic_id: int | None = None
    document_id: str | None = None
    attempt_id: str | None = None


class ActivityItem(BaseModel):
    kind: Literal["upload", "quiz"]
    title: str
    detail: str
    at: datetime
    ref_id: str


class ProgressSummary(BaseModel):
    documents_ready: int
    documents_total: int
    attempts_submitted: int
    attempts_in_progress: int
    questions_answered: int
    questions_correct: int
    average_accuracy: float | None
    min_answers_for_accuracy: int
    min_answers_per_topic: int
    topics: list[TopicProgress]
    weak_topics: list[TopicProgress]
    insufficient_topics: list[TopicProgress]
    recommendations: list[Recommendation]
    recent_activity: list[ActivityItem]
    accuracy_trend: list[dict]


class IncorrectItem(BaseModel):
    question_id: str
    attempt_id: str
    attempt_title: str
    answered_at: datetime | None
    stem: str
    options: list[str]
    selected_index: int | None
    correct_index: int
    explanation: str
    evidence: str
    location_type: str
    location_start: int
    topic_id: int | None
    topic_title: str | None
    document_id: str
    times_missed: int
