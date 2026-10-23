"""Progress analytics computed from persisted quiz responses."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Question, QuizAttempt, QuizItem, Topic, Workspace
from app.schemas import ActivityItem, IncorrectItem, ProgressSummary, Recommendation, TopicProgress

MIN_ANSWERS_FOR_ACCURACY = 5  # overall accuracy is hidden until at least this many questions were attempted
MIN_ANSWERS_PER_TOPIC = 5  # a topic needs this many attempted questions before it can be called weak or strong
WEAK_BELOW = 0.6
STRONG_FROM = 0.8


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _submitted_rows(db: Session, workspace: Workspace):
    """(item, question, attempt) rows for every question in a submitted attempt, oldest first."""
    return db.execute(
        select(QuizItem, Question, QuizAttempt)
        .join(Question, Question.id == QuizItem.question_id)
        .join(QuizAttempt, QuizAttempt.id == QuizItem.attempt_id)
        .where(QuizAttempt.workspace_id == workspace.id, QuizAttempt.status == "submitted")
        .order_by(QuizAttempt.submitted_at, QuizItem.position)
    ).all()


def summary(db: Session, workspace: Workspace) -> ProgressSummary:
    docs = db.scalars(
        select(Document).where(Document.workspace_id == workspace.id).order_by(Document.created_at.desc())
    ).all()
    ready_ids = [d.id for d in docs if d.status == "ready"]
    doc_names = {d.id: d.name for d in docs}
    topics = (
        db.scalars(
            select(Topic).where(Topic.document_id.in_(ready_ids)).order_by(Topic.document_id, Topic.position)
        ).all()
        if ready_ids
        else []
    )
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.workspace_id == workspace.id)).all()
    submitted = sorted((a for a in attempts if a.status == "submitted"), key=lambda a: _aware(a.submitted_at))
    rows = _submitted_rows(db, workspace)

    per_topic: dict[int, dict] = {}
    presented = correct_total = 0
    for item, question, attempt in rows:
        presented += 1
        correct_total += int(bool(item.is_correct))
        if question.topic_id is None:
            continue
        stats = per_topic.setdefault(question.topic_id, {"attempted": 0, "correct": 0, "last": None})
        stats["attempted"] += 1
        stats["correct"] += int(bool(item.is_correct))
        stats["last"] = _aware(attempt.submitted_at)

    topic_progress: list[TopicProgress] = []
    for t in topics:
        s = per_topic.get(t.id, {"attempted": 0, "correct": 0, "last": None})
        accuracy = s["correct"] / s["attempted"] if s["attempted"] else None
        if s["attempted"] == 0:
            status = "not_started"
        elif s["attempted"] < MIN_ANSWERS_PER_TOPIC:
            status = "insufficient"
        elif accuracy < WEAK_BELOW:
            status = "weak"
        elif accuracy < STRONG_FROM:
            status = "developing"
        else:
            status = "strong"
        topic_progress.append(
            TopicProgress(
                topic_id=t.id,
                topic_title=t.title,
                document_id=t.document_id,
                document_name=doc_names.get(t.document_id, ""),
                attempted=s["attempted"],
                correct=s["correct"],
                accuracy=round(accuracy, 3) if accuracy is not None else None,
                status=status,
                last_practiced=s["last"],
            )
        )

    weak = sorted((t for t in topic_progress if t.status == "weak"), key=lambda t: t.accuracy or 0)
    insufficient = [t for t in topic_progress if t.status in ("insufficient", "not_started")]
    insufficient.sort(key=lambda t: (t.status != "insufficient", t.attempted))

    recs: list[Recommendation] = []
    if not docs:
        recs.append(
            Recommendation(
                kind="upload",
                title="Upload your first study material",
                detail="Add lecture notes as PDF, DOCX or PPTX to generate topics and questions.",
            )
        )
    elif not ready_ids:
        recs.append(
            Recommendation(
                kind="upload",
                title="Upload a document that can be processed",
                detail="None of your uploads were processed successfully. Check the error shown in My Materials.",
            )
        )
    elif not submitted:
        recs.append(
            Recommendation(
                kind="start",
                title="Take your first practice test",
                detail="A short quiz gives StudyForge the data it needs to find weak topics.",
                document_id=ready_ids[0],
            )
        )
    for t in weak[:3]:
        recs.append(
            Recommendation(
                kind="revise",
                title=f"Revise {t.topic_title}",
                detail=f"{t.correct} of {t.attempted} answered correctly ({round(100 * (t.accuracy or 0))}%). Read the "
                "learning guide, then practise this topic again.",
                topic_id=t.topic_id,
                document_id=t.document_id,
            )
        )
    last_with_mistakes = next((a for a in reversed(submitted) if a.correct_count < a.total), None)
    if last_with_mistakes is not None:
        missed = last_with_mistakes.total - last_with_mistakes.correct_count
        recs.append(
            Recommendation(
                kind="retry",
                title="Retry the questions you missed",
                detail=f'{missed} question(s) from "{last_with_mistakes.title}" were incorrect or unanswered.',
                attempt_id=last_with_mistakes.id,
            )
        )
    if submitted:
        for t in [t for t in insufficient if t.status == "insufficient"][:2] + [
            t for t in insufficient if t.status == "not_started"
        ][:2]:
            recs.append(
                Recommendation(
                    kind="practice",
                    title=f"Practise {t.topic_title}",
                    detail=(
                        "Not practised yet."
                        if t.status == "not_started"
                        else f"Only {t.attempted} question(s) attempted so far — not enough to judge this topic."
                    ),
                    topic_id=t.topic_id,
                    document_id=t.document_id,
                )
            )
    strong = [t for t in topic_progress if t.status == "strong"]
    if strong:
        recs.append(
            Recommendation(
                kind="maintain",
                title=f"Keep {strong[0].topic_title} fresh",
                detail="You are scoring well here. A quick revision before the exam is enough.",
                topic_id=strong[0].topic_id,
                document_id=strong[0].document_id,
            )
        )

    activity: list[ActivityItem] = []
    for d in docs[:10]:
        detail = {
            "ready": f"{d.topic_count} topics · {d.question_count} questions",
            "failed": "Processing failed",
            "processing": "Processing",
        }.get(d.status, d.status)
        activity.append(ActivityItem(kind="upload", title=d.name, detail=detail, at=_aware(d.created_at), ref_id=d.id))
    for a in submitted[-10:]:
        activity.append(
            ActivityItem(
                kind="quiz",
                title=a.title,
                detail=f"Scored {a.correct_count}/{a.total}",
                at=_aware(a.submitted_at),
                ref_id=a.id,
            )
        )
    activity.sort(key=lambda x: x.at, reverse=True)

    trend = [
        {
            "attempt_id": a.id,
            "title": a.title,
            "score_percent": round(100 * a.correct_count / a.total, 1) if a.total else 0,
            "submitted_at": _aware(a.submitted_at).isoformat(),
        }
        for a in submitted[-15:]
    ]
    return ProgressSummary(
        documents_ready=len(ready_ids),
        documents_total=len(docs),
        attempts_submitted=len(submitted),
        attempts_in_progress=sum(1 for a in attempts if a.status == "in_progress"),
        questions_answered=presented,
        questions_correct=correct_total,
        average_accuracy=round(correct_total / presented, 3) if presented >= MIN_ANSWERS_FOR_ACCURACY else None,
        min_answers_for_accuracy=MIN_ANSWERS_FOR_ACCURACY,
        min_answers_per_topic=MIN_ANSWERS_PER_TOPIC,
        topics=topic_progress,
        weak_topics=weak,
        insufficient_topics=insufficient,
        recommendations=recs,
        recent_activity=activity[:8],
        accuracy_trend=trend,
    )


def incorrect_questions(db: Session, workspace: Workspace, limit: int = 50) -> list[IncorrectItem]:
    """Questions whose most recent answer was wrong or blank (later correct answers resolve them)."""
    latest: dict[str, tuple] = {}
    misses: dict[str, int] = {}
    for item, question, attempt in _submitted_rows(db, workspace):
        latest[question.id] = (item, question, attempt)
        if not item.is_correct:
            misses[question.id] = misses.get(question.id, 0) + 1
    topic_titles = (
        dict(
            db.execute(
                select(Topic.id, Topic.title).where(
                    Topic.id.in_({q.topic_id for _, q, _ in latest.values() if q.topic_id})
                )
            ).all()
        )
        if latest
        else {}
    )
    out: list[IncorrectItem] = []
    for item, question, attempt in sorted(latest.values(), key=lambda r: _aware(r[2].submitted_at), reverse=True):
        if item.is_correct:
            continue
        out.append(
            IncorrectItem(
                question_id=question.id,
                attempt_id=attempt.id,
                attempt_title=attempt.title,
                answered_at=_aware(attempt.submitted_at),
                stem=question.stem,
                options=question.options or [],
                selected_index=item.selected_index,
                correct_index=question.correct_index,
                explanation=question.explanation,
                evidence=question.evidence,
                location_type=question.location_type,
                location_start=question.location_start,
                topic_id=question.topic_id,
                topic_title=topic_titles.get(question.topic_id),
                document_id=question.document_id,
                times_missed=misses.get(question.id, 1),
            )
        )
        if len(out) >= limit:
            break
    return out
