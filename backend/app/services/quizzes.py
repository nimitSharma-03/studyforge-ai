"""Quiz engine: assembling practice tests, saving answers and server-side scoring."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.models import Document, Question, QuizAttempt, QuizItem, Topic, Workspace, utcnow
from app.schemas import (
    QuizCreate,
    QuizHistoryItem,
    QuizOut,
    QuizQuestionOut,
    QuizResult,
    QuizResultItem,
    ResponseIn,
    TopicScore,
)

MODE_PRESETS = {
    # mode: (default question count, default timer minutes, default difficulties)
    "mid_sem": (15, 30, ["easy", "medium"]),
    "end_sem": (30, 60, ["easy", "medium", "hard"]),
    "topic": (10, None, []),
    "custom": (10, None, []),
    "retry": (100, None, []),
}
MODE_TITLES = {
    "mid_sem": "Mid-semester practice",
    "end_sem": "End-semester practice",
    "topic": "Topic practice",
    "custom": "Custom quiz",
    "retry": "Retry incorrect questions",
}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def get_attempt(db: Session, workspace: Workspace, attempt_id: str) -> QuizAttempt:
    attempt = db.scalar(
        select(QuizAttempt)
        .where(QuizAttempt.id == attempt_id)
        .options(selectinload(QuizAttempt.items).selectinload(QuizItem.question).selectinload(Question.topic))
    )
    if attempt is None or attempt.workspace_id != workspace.id:
        raise AppError(404, "quiz_not_found", "Quiz not found.")
    return attempt


def _balanced_sample(questions: list[Question], count: int, rng: random.Random) -> list[Question]:
    """Pick questions round-robin across topics so a quiz covers the syllabus evenly."""
    by_topic: dict[int | None, list[Question]] = defaultdict(list)
    for q in questions:
        by_topic[q.topic_id].append(q)
    for group in by_topic.values():
        rng.shuffle(group)
    topic_order = list(by_topic)
    rng.shuffle(topic_order)
    picked: list[Question] = []
    while len(picked) < count and any(by_topic.values()):
        for topic_id in topic_order:
            if by_topic[topic_id]:
                picked.append(by_topic[topic_id].pop())
                if len(picked) == count:
                    break
    rng.shuffle(picked)
    return picked


def create_quiz(db: Session, workspace: Workspace, req: QuizCreate) -> QuizAttempt:
    rng = random.Random()
    default_count, default_timer, default_difficulties = MODE_PRESETS[req.mode]
    count = req.count or default_count
    timer = req.time_limit_minutes if req.time_limit_minutes is not None else default_timer

    if req.mode == "retry":
        if not req.source_attempt_id:
            raise AppError(422, "source_required", "Choose the quiz whose incorrect answers you want to retry.")
        source = get_attempt(db, workspace, req.source_attempt_id)
        if source.status != "submitted":
            raise AppError(409, "quiz_not_submitted", "Submit the quiz before retrying its incorrect questions.")
        questions = [i.question for i in source.items if not i.is_correct]
        if not questions:
            raise AppError(422, "nothing_to_retry", "Every question in that quiz was answered correctly.")
        document_ids = sorted({q.document_id for q in questions})
        picked = questions[:count]
        rng.shuffle(picked)
        title = req.title or f"Retry: {source.title}"
    else:
        if not req.document_ids:
            raise AppError(422, "documents_required", "Select at least one document.")
        docs = db.scalars(
            select(Document).where(Document.id.in_(req.document_ids), Document.workspace_id == workspace.id)
        ).all()
        if len(docs) != len(set(req.document_ids)):
            raise AppError(404, "document_not_found", "One or more selected documents were not found.")
        if any(d.status != "ready" for d in docs):
            raise AppError(409, "document_not_ready", "All selected documents must be processed successfully.")
        document_ids = [d.id for d in docs]
        topic_filter: set[int] | None = None
        if req.mode == "topic" and not req.topic_ids:
            raise AppError(422, "topics_required", "Select at least one topic for topic practice.")
        if req.topic_ids:
            valid = set(
                db.scalars(select(Topic.id).where(Topic.id.in_(req.topic_ids), Topic.document_id.in_(document_ids)))
            )
            if len(valid) != len(set(req.topic_ids)):
                raise AppError(404, "topic_not_found", "One or more selected topics were not found.")
            topic_filter = valid
        elif req.mode == "mid_sem":
            # Mid-semester exams conventionally cover the first half of the syllabus.
            topic_filter = set()
            for d in docs:
                ids = list(db.scalars(select(Topic.id).where(Topic.document_id == d.id).order_by(Topic.position)))
                topic_filter |= set(ids[: max(1, math.ceil(len(ids) / 2))])
        stmt = select(Question).where(Question.document_id.in_(document_ids), Question.question_type == "mcq")
        if topic_filter is not None:
            stmt = stmt.where(Question.topic_id.in_(topic_filter))
        pool = list(db.scalars(stmt))
        difficulties = req.difficulties or default_difficulties
        preferred = [q for q in pool if not difficulties or q.difficulty in difficulties]
        if req.difficulties:
            pool = preferred  # explicit choice is a hard filter
        elif len(preferred) < count:
            # Presets are soft: top up with other difficulties rather than giving a short quiz.
            rest = [q for q in pool if q not in preferred]
            preferred = preferred + _balanced_sample(rest, count - len(preferred), rng)
            pool = preferred
        else:
            pool = preferred
        if not pool:
            raise AppError(
                422,
                "no_questions",
                "No multiple-choice questions match these settings. Try other topics or difficulty levels.",
            )
        picked = _balanced_sample(pool, count, rng)
        title = req.title or MODE_TITLES[req.mode]
        if req.mode == "topic" and topic_filter and len(topic_filter) == 1:
            topic = db.get(Topic, next(iter(topic_filter)))
            title = req.title or f"Topic practice: {topic.title}"

    attempt = QuizAttempt(
        workspace_id=workspace.id,
        title=title[:255],
        mode=req.mode,
        document_ids=document_ids,
        time_limit_minutes=timer,
        status="in_progress",
        total=len(picked),
    )
    db.add(attempt)
    db.flush()
    for position, q in enumerate(picked):
        db.add(QuizItem(attempt_id=attempt.id, question_id=q.id, position=position))
    db.commit()
    return get_attempt(db, workspace, attempt.id)


def quiz_out(attempt: QuizAttempt) -> QuizOut:
    """Exam view: options only. Correct answers and explanations are never included."""
    return QuizOut(
        id=attempt.id,
        title=attempt.title,
        mode=attempt.mode,
        status=attempt.status,
        time_limit_minutes=attempt.time_limit_minutes,
        created_at=_aware(attempt.created_at),
        total=attempt.total,
        document_ids=attempt.document_ids,
        questions=[
            QuizQuestionOut(
                question_id=i.question_id,
                position=i.position,
                stem=i.question.stem,
                options=i.question.options or [],
                topic_id=i.question.topic_id,
                topic_title=i.question.topic.title if i.question.topic else None,
                difficulty=i.question.difficulty,
                category=i.question.category,
                selected_index=i.selected_index,
                marked_for_review=i.marked_for_review,
            )
            for i in attempt.items
        ],
    )


def _apply_responses(attempt: QuizAttempt, responses: list[ResponseIn]) -> None:
    items = {i.question_id: i for i in attempt.items}
    for r in responses:
        item = items.get(r.question_id)
        if item is None:
            raise AppError(422, "unknown_question", "A response refers to a question that is not in this quiz.")
        item.selected_index = r.selected_index
        item.marked_for_review = r.marked_for_review


def save_responses(db: Session, workspace: Workspace, attempt_id: str, responses: list[ResponseIn]) -> QuizAttempt:
    attempt = get_attempt(db, workspace, attempt_id)
    if attempt.status != "in_progress":
        raise AppError(409, "already_submitted", "This quiz has already been submitted.")
    _apply_responses(attempt, responses)
    db.commit()
    return attempt


def submit(db: Session, workspace: Workspace, attempt_id: str, responses: list[ResponseIn]) -> QuizAttempt:
    attempt = get_attempt(db, workspace, attempt_id)
    # Atomically claim the attempt: only one concurrent submission can flip in_progress -> submitted.
    claimed = db.execute(
        update(QuizAttempt)
        .where(QuizAttempt.id == attempt.id, QuizAttempt.status == "in_progress")
        .values(status="submitted")
        .execution_options(synchronize_session=False)
    ).rowcount
    if not claimed:
        db.rollback()
        raise AppError(409, "already_submitted", "This quiz has already been submitted.", {"quiz_id": attempt.id})
    try:
        _apply_responses(attempt, responses)
        correct = answered = 0
        for item in attempt.items:
            q = item.question
            if item.selected_index is None:
                item.is_correct = False
                continue
            answered += 1
            # Score against the stored answer key only; nothing from the client decides correctness.
            item.is_correct = item.selected_index == q.correct_index
            correct += int(item.is_correct)
        now = utcnow()
        attempt.status = "submitted"
        attempt.correct_count = correct
        attempt.answered_count = answered
        attempt.submitted_at = now
        elapsed = int((now - _aware(attempt.created_at)).total_seconds())
        attempt.duration_seconds = max(0, elapsed)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_attempt(db, workspace, attempt.id)


def _status(item: QuizItem) -> str:
    if item.selected_index is None:
        return "unanswered"
    return "correct" if item.is_correct else "incorrect"


def quiz_result(attempt: QuizAttempt) -> QuizResult:
    if attempt.status != "submitted":
        raise AppError(409, "quiz_not_submitted", "Results are available after the quiz is submitted.")
    items: list[QuizResultItem] = []
    breakdown: dict[int | None, TopicScore] = {}
    for i in attempt.items:
        q = i.question
        topic_title = q.topic.title if q.topic else "General"
        items.append(
            QuizResultItem(
                question_id=q.id,
                position=i.position,
                stem=q.stem,
                options=q.options or [],
                selected_index=i.selected_index,
                correct_index=q.correct_index,
                status=_status(i),
                explanation=q.explanation,
                option_notes=q.option_notes,
                evidence=q.evidence,
                location_type=q.location_type,
                location_start=q.location_start,
                location_end=q.location_end,
                topic_id=q.topic_id,
                topic_title=topic_title,
                document_id=q.document_id,
                difficulty=q.difficulty,
                category=q.category,
                marked_for_review=i.marked_for_review,
            )
        )
        score = breakdown.setdefault(
            q.topic_id, TopicScore(topic_id=q.topic_id, topic_title=topic_title, correct=0, total=0)
        )
        score.total += 1
        score.correct += int(bool(i.is_correct))
    total = attempt.total or len(items)
    return QuizResult(
        id=attempt.id,
        title=attempt.title,
        mode=attempt.mode,
        status=attempt.status,
        total=total,
        correct_count=attempt.correct_count,
        answered_count=attempt.answered_count,
        incorrect_count=attempt.answered_count - attempt.correct_count,
        unanswered_count=total - attempt.answered_count,
        score_percent=round(100 * attempt.correct_count / total, 1) if total else 0.0,
        duration_seconds=attempt.duration_seconds,
        time_limit_minutes=attempt.time_limit_minutes,
        created_at=_aware(attempt.created_at),
        submitted_at=_aware(attempt.submitted_at),
        items=items,
        topic_breakdown=sorted(breakdown.values(), key=lambda s: s.topic_title),
    )


def history(db: Session, workspace: Workspace, limit: int = 50) -> list[QuizHistoryItem]:
    attempts = db.scalars(
        select(QuizAttempt)
        .where(QuizAttempt.workspace_id == workspace.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(limit)
    ).all()
    return [
        QuizHistoryItem(
            id=a.id,
            title=a.title,
            mode=a.mode,
            status=a.status,
            total=a.total,
            correct_count=a.correct_count,
            answered_count=a.answered_count,
            score_percent=round(100 * a.correct_count / a.total, 1) if a.status == "submitted" and a.total else None,
            created_at=_aware(a.created_at),
            submitted_at=_aware(a.submitted_at),
            duration_seconds=a.duration_seconds,
            document_ids=a.document_ids,
        )
        for a in attempts
    ]


def delete_attempt(db: Session, workspace: Workspace, attempt_id: str) -> None:
    attempt = get_attempt(db, workspace, attempt_id)
    db.delete(attempt)
    db.commit()
