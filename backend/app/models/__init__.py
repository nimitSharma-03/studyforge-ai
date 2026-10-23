"""ORM models. Every user-owned row hangs off a Workspace for isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list[Document]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    attempts: Mapped[list[QuizAttempt]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(8))  # pdf | docx | pptx
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="processing")  # processing | ready | failed
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    unit_count: Mapped[int] = mapped_column(Integer, default=0)  # pages, slides or sections
    unit_label: Mapped[str] = mapped_column(String(16), default="page")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    topic_count: Mapped[int] = mapped_column(Integer, default=0)
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_question_count: Mapped[int] = mapped_column(Integer, default=0)
    heading_count: Mapped[int] = mapped_column(Integer, default=0)
    segmentation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    processing_ms: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    topics: Mapped[list[Topic]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Topic.position"
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Chunk.position"
    )
    questions: Mapped[list[Question]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    title_source: Mapped[str] = mapped_column(String(16), default="heading")  # heading | keywords
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    location_type: Mapped[str] = mapped_column(String(16))
    location_start: Mapped[int] = mapped_column(Integer)
    location_end: Mapped[int] = mapped_column(Integer)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    guide: Mapped[dict] = mapped_column(JSON, default=dict)

    document: Mapped[Document] = relationship(back_populates="topics")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="topic", order_by="Chunk.position")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    location_type: Mapped[str] = mapped_column(String(16))
    location_start: Mapped[int] = mapped_column(Integer)
    location_end: Mapped[int] = mapped_column(Integer)
    word_count: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped[Document] = relationship(back_populates="chunks")
    topic: Mapped[Topic | None] = relationship(back_populates="chunks")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (Index("ix_questions_doc_type", "document_id", "question_type"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=True)
    question_type: Mapped[str] = mapped_column(String(16))  # mcq | short_answer | long_answer
    category: Mapped[str] = mapped_column(String(16))  # definition | factual | conceptual | application | revision
    difficulty: Mapped[str] = mapped_column(String(8))  # easy | medium | hard
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    option_notes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    location_type: Mapped[str] = mapped_column(String(16))
    location_start: Mapped[int] = mapped_column(Integer)
    location_end: Mapped[int] = mapped_column(Integer)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    stem_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document] = relationship(back_populates="questions")
    topic: Mapped[Topic | None] = relationship()


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16))  # mid_sem | end_sem | topic | custom | retry
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress | submitted
    total: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="attempts")
    items: Mapped[list[QuizItem]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", order_by="QuizItem.position"
    )


class QuizItem(Base):
    __tablename__ = "quiz_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    selected_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)

    attempt: Mapped[QuizAttempt] = relationship(back_populates="items")
    question: Mapped[Question] = relationship()
