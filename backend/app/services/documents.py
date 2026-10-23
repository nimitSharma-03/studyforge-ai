"""Document ingestion, lookup and deletion."""

from __future__ import annotations

import hashlib
import logging
import time

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.models import Chunk, Document, Question, QuizAttempt, QuizItem, Topic, Workspace
from app.nlp.extract import UNIT_LABELS, ExtractionError, detect_file_type, extract
from app.nlp.pipeline import process
from app.nlp.retrieval import index_cache

logger = logging.getLogger("studyforge.ingest")

MAX_NAME = 200


def display_name(filename: str) -> str:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    cleaned = " ".join(stem.replace("_", " ").split())
    return (cleaned or "Untitled document")[:MAX_NAME]


def safe_filename(filename: str) -> str:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(c for c in base if c.isalnum() or c in "._- ()")[:MAX_NAME] or "upload"


def get_document(db: Session, workspace: Workspace, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace.id:
        # Same response for "missing" and "belongs to someone else" so IDs cannot be probed.
        raise AppError(404, "document_not_found", "Document not found.")
    return doc


def get_ready_document(db: Session, workspace: Workspace, document_id: str) -> Document:
    doc = get_document(db, workspace, document_id)
    if doc.status != "ready":
        raise AppError(409, "document_not_ready", "This document has not been processed successfully.")
    return doc


def ingest(
    db: Session, workspace: Workspace, filename: str, data: bytes, *, is_sample: bool = False
) -> tuple[Document, bool]:
    """Validate, extract and analyse an uploaded file. Returns (document, was_duplicate)."""
    settings = get_settings()
    if not data:
        raise AppError(400, "empty_file", "The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise AppError(413, "file_too_large", f"Files must be {settings.max_upload_mb} MB or smaller.")
    try:
        file_type = detect_file_type(filename, data)
    except ExtractionError as exc:
        status = 415 if exc.code == "unsupported_type" else 422
        raise AppError(status, exc.code, exc.message) from exc

    content_hash = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(Document).where(
            Document.workspace_id == workspace.id,
            Document.content_hash == content_hash,
            Document.status == "ready",
        )
    )
    if existing is not None:
        return existing, True

    count = db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == workspace.id)) or 0
    if count >= settings.max_documents_per_workspace:
        raise AppError(
            409,
            "quota_exceeded",
            f"This workspace already has {count} documents (limit {settings.max_documents_per_workspace}). "
            "Delete a document to upload another.",
        )

    doc = Document(
        workspace_id=workspace.id,
        name=display_name(filename),
        original_filename=safe_filename(filename),
        file_type=file_type,
        size_bytes=len(data),
        content_hash=content_hash,
        status="processing",
        is_sample=is_sample,
        unit_label=UNIT_LABELS[file_type],
        warnings=[],
        stats={},
    )
    db.add(doc)
    db.commit()

    started = time.monotonic()
    try:
        extraction = extract(filename, data, max_pages=settings.max_pages)
        processed = process(extraction, timeout_seconds=settings.processing_timeout_seconds)
    except ExtractionError as exc:
        _mark_failed(db, doc, exc.code, exc.message, started)
        logger.info("document %s failed extraction: %s", doc.id, exc.code)
        return doc, False
    except Exception:  # noqa: BLE001 - any parser bug must not leave the document stuck in "processing"
        logger.exception("document %s failed with an unexpected error", doc.id)
        _mark_failed(
            db, doc, "internal_error", "The document could not be processed due to an internal error.", started
        )
        return doc, False

    try:
        _store_results(db, doc, processed)
        doc.processing_ms = int((time.monotonic() - started) * 1000)
        doc.status = "ready"
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("document %s failed while saving results", doc.id)
        _mark_failed(db, doc, "internal_error", "The analysis results could not be saved.", started)
        return doc, False
    logger.info(
        "document %s processed: type=%s units=%s topics=%s chunks=%s questions=%s in %sms",
        doc.id,
        doc.file_type,
        doc.unit_count,
        doc.topic_count,
        doc.chunk_count,
        doc.question_count,
        doc.processing_ms,
    )
    return doc, False


def _mark_failed(db: Session, doc: Document, code: str, message: str, started: float) -> None:
    doc = db.merge(doc)
    doc.status = "failed"
    doc.error_code = code
    doc.error_message = message
    doc.processing_ms = int((time.monotonic() - started) * 1000)
    db.commit()


def _store_results(db: Session, doc: Document, processed) -> None:
    label = processed.unit_label
    topic_ids: dict[int, int] = {}
    for position, t in enumerate(processed.topics):
        topic = Topic(
            document_id=doc.id,
            position=position,
            title=t.title[:255],
            title_source=t.title_source,
            keywords=t.keywords,
            location_type=label,
            location_start=t.location_start,
            location_end=t.location_end,
            word_count=t.word_count,
            guide=t.guide,
        )
        db.add(topic)
        db.flush()
        topic_ids[t.section_index] = topic.id
    for position, c in enumerate(processed.chunks):
        db.add(
            Chunk(
                document_id=doc.id,
                topic_id=topic_ids.get(c.section_index),
                position=position,
                heading=(c.heading or "")[:255] or None,
                text=c.text,
                location_type=label,
                location_start=c.location_start,
                location_end=c.location_end,
                word_count=c.words,
            )
        )
    for q in processed.questions:
        db.add(
            Question(
                document_id=doc.id,
                topic_id=topic_ids.get(q.section_index),
                question_type=q.question_type,
                category=q.category,
                difficulty=q.difficulty,
                stem=q.stem,
                options=q.options,
                correct_index=q.correct_index,
                option_notes=q.option_notes,
                answer_text=q.answer_text,
                explanation=q.explanation,
                evidence=q.evidence,
                location_type=label,
                location_start=q.location,
                location_end=q.location_end,
                quality_score=q.quality,
                stem_hash=q.stem_hash,
            )
        )
    doc.unit_label = label
    doc.unit_count = processed.unit_count
    doc.word_count = processed.word_count
    doc.heading_count = processed.heading_count
    doc.segmentation_method = processed.segmentation_method
    doc.topic_count = len(processed.topics)
    doc.chunk_count = len(processed.chunks)
    doc.question_count = len(processed.questions)
    doc.rejected_question_count = processed.stats.get("rejected_total", 0)
    doc.warnings = processed.warnings
    doc.stats = processed.stats
    doc.error_code = None
    doc.error_message = None


def attempts_using_document(db: Session, workspace: Workspace, document_id: str) -> list[str]:
    rows = db.scalars(
        select(QuizItem.attempt_id)
        .join(Question, Question.id == QuizItem.question_id)
        .join(QuizAttempt, QuizAttempt.id == QuizItem.attempt_id)
        .where(Question.document_id == document_id, QuizAttempt.workspace_id == workspace.id)
        .distinct()
    )
    return list(rows)


def delete_document(db: Session, workspace: Workspace, doc: Document) -> dict:
    """Delete a document and everything derived from it, including quiz attempts that used it."""
    attempt_ids = attempts_using_document(db, workspace, doc.id)
    counts = {
        "topics": doc.topic_count,
        "questions": doc.question_count,
        "quiz_attempts": len(attempt_ids),
    }
    if attempt_ids:
        db.execute(delete(QuizItem).where(QuizItem.attempt_id.in_(attempt_ids)))
        db.execute(delete(QuizAttempt).where(QuizAttempt.id.in_(attempt_ids)))
    db.execute(
        delete(QuizItem).where(QuizItem.question_id.in_(select(Question.id).where(Question.document_id == doc.id)))
    )
    db.execute(delete(Question).where(Question.document_id == doc.id))
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    db.execute(delete(Topic).where(Topic.document_id == doc.id))
    db.execute(delete(Document).where(Document.id == doc.id))
    db.commit()
    index_cache.invalidate_prefix(doc.id)
    return counts
