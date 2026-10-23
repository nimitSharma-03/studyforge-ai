"""Progress, revision and export endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_workspace
from app.api.questions import filtered_questions
from app.db.session import get_db
from app.models import Document, Question, Topic, Workspace
from app.schemas import IncorrectItem, ProgressSummary
from app.services import documents as doc_service
from app.services import exports
from app.services import progress as progress_service
from app.services import quizzes as quiz_service

router = APIRouter(tags=["progress"])


@router.get("/progress/summary", response_model=ProgressSummary)
def progress_summary(workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> ProgressSummary:
    return progress_service.summary(db, workspace)


@router.get("/progress/incorrect", response_model=list[IncorrectItem])
def incorrect_questions(
    limit: int = Query(50, ge=1, le=200), workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> list[IncorrectItem]:
    return progress_service.incorrect_questions(db, workspace, limit)


def _download(content: bytes, fmt: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=exports.FORMATS[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


ExportFormat = Literal["md", "txt", "pdf"]


@router.get("/exports/documents/{document_id}/notes")
def export_notes(
    document_id: str,
    format: ExportFormat = "md",
    mode: Literal["concise", "detailed"] = "detailed",
    topic_id: list[int] = Query(default=[]),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> Response:
    doc = doc_service.get_ready_document(db, workspace, document_id)
    topics = [t for t in doc.topics if not topic_id or t.id in topic_id]
    blocks = exports.revision_notes(doc, topics, detailed=mode == "detailed")
    return _download(
        exports.render(blocks, format), format, exports.export_filename(doc.name, f"revision-{mode}", format)
    )


@router.get("/exports/documents/{document_id}/questions")
def export_questions(
    document_id: str,
    format: ExportFormat = "md",
    answers: bool = True,
    topic_id: list[int] = Query(default=[]),
    difficulty: list[str] = Query(default=[]),
    question_type: list[str] = Query(default=[]),
    category: list[str] = Query(default=[]),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> Response:
    doc = doc_service.get_ready_document(db, workspace, document_id)
    stmt = filtered_questions(db, doc.id, topic_id, difficulty, question_type, category)
    questions = list(db.scalars(stmt.order_by(Question.topic_id, Question.location_start)))
    titles = dict(db.execute(select(Topic.id, Topic.title).where(Topic.document_id == doc.id)).all())
    blocks = exports.question_bank(doc, questions, titles, include_answers=answers)
    return _download(exports.render(blocks, format), format, exports.export_filename(doc.name, "question-bank", format))


@router.get("/exports/quizzes/{quiz_id}")
def export_quiz(
    quiz_id: str,
    format: ExportFormat = "md",
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> Response:
    result = quiz_service.quiz_result(quiz_service.get_attempt(db, workspace, quiz_id))
    labels = dict(
        db.execute(
            select(Document.id, Document.unit_label).where(Document.id.in_({i.document_id for i in result.items}))
        ).all()
    )
    blocks = exports.quiz_report(result, labels)
    return _download(exports.render(blocks, format), format, exports.export_filename(result.title, "results", format))
