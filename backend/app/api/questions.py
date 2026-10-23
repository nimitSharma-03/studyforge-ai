"""Question bank endpoints."""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_workspace
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Question, Topic, Workspace
from app.schemas import QuestionBankPage, QuestionOut, QuestionSetRequest, QuestionSetResponse
from app.services import documents as doc_service

router = APIRouter(tags=["questions"])


def _out(questions: list[Question], titles: dict[int, str]) -> list[QuestionOut]:
    return [QuestionOut.model_validate(q).model_copy(update={"topic_title": titles.get(q.topic_id)}) for q in questions]


def _titles(db: Session, document_id: str) -> dict[int, str]:
    return dict(db.execute(select(Topic.id, Topic.title).where(Topic.document_id == document_id)).all())


def filtered_questions(
    db: Session,
    document_id: str,
    topic_ids: list[int],
    difficulties: list[str],
    question_types: list[str],
    categories: list[str],
):
    stmt = select(Question).where(Question.document_id == document_id)
    if topic_ids:
        stmt = stmt.where(Question.topic_id.in_(topic_ids))
    if difficulties:
        stmt = stmt.where(Question.difficulty.in_(difficulties))
    if question_types:
        stmt = stmt.where(Question.question_type.in_(question_types))
    if categories:
        stmt = stmt.where(Question.category.in_(categories))
    return stmt


@router.get("/questions", response_model=QuestionBankPage)
def question_bank(
    document_id: str,
    topic_id: list[int] = Query(default=[]),
    difficulty: list[str] = Query(default=[]),
    question_type: list[str] = Query(default=[]),
    category: list[str] = Query(default=[]),
    search: str | None = Query(default=None, max_length=100),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> QuestionBankPage:
    """Browse validated questions with answers (study mode). Exam mode uses /quizzes, which hides answers."""
    doc = doc_service.get_ready_document(db, workspace, document_id)
    stmt = filtered_questions(db, doc.id, topic_id, difficulty, question_type, category)
    if search:
        stmt = stmt.where(Question.stem.ilike(f"%{search.strip()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Question.topic_id, Question.question_type, Question.location_start).offset(offset).limit(limit)
    ).all()
    counts: dict[str, dict[str, int]] = {"question_type": {}, "difficulty": {}, "category": {}}
    for field in counts:
        column = getattr(Question, field)
        for value, n in db.execute(select(column, func.count()).where(Question.document_id == doc.id).group_by(column)):
            counts[field][value] = n
    return QuestionBankPage(
        items=_out(rows, _titles(db, doc.id)), total=total, offset=offset, limit=limit, counts=counts
    )


@router.post("/questions/generate", response_model=QuestionSetResponse)
def generate_question_set(
    body: QuestionSetRequest, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> QuestionSetResponse:
    """Assemble a question set from the validated questions generated when the document was processed."""
    doc = doc_service.get_ready_document(db, workspace, body.document_id)
    if body.topic_ids:
        valid = set(db.scalars(select(Topic.id).where(Topic.id.in_(body.topic_ids), Topic.document_id == doc.id)))
        if len(valid) != len(set(body.topic_ids)):
            raise AppError(404, "topic_not_found", "One or more selected topics were not found.")
    pool = list(
        db.scalars(
            filtered_questions(db, doc.id, body.topic_ids, body.difficulties, body.question_types, body.categories)
        )
    )
    rng = random.Random(body.seed)
    rng.shuffle(pool)
    picked = sorted(pool[: body.count], key=lambda q: (q.question_type != "mcq", q.question_type, q.location_start))
    if not pool:
        message = "No validated questions match these filters. Try selecting more topics, types or difficulty levels."
    elif len(pool) < body.count:
        message = (
            f"Only {len(pool)} validated question(s) match these filters, so the set is smaller than requested. "
            "Questions that failed quality checks are never padded in."
        )
    else:
        message = f"Selected {len(picked)} of {len(pool)} matching validated questions."
    return QuestionSetResponse(
        questions=_out(picked, _titles(db, doc.id)), requested=body.count, available=len(pool), message=message
    )
