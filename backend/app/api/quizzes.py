"""Practice test endpoints. Answer keys are only returned after submission."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_workspace
from app.config import get_settings
from app.core.ratelimit import limiter
from app.db.session import get_db
from app.models import Workspace
from app.schemas import QuizCreate, QuizHistoryItem, QuizOut, QuizResult, SaveResponses, SubmitRequest
from app.services import quizzes as quiz_service

router = APIRouter(tags=["quizzes"])


@router.post("/quizzes", response_model=QuizOut, status_code=201)
def create_quiz(
    body: QuizCreate, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> QuizOut:
    limiter.check("quiz", workspace.id, get_settings().quizzes_per_hour)
    return quiz_service.quiz_out(quiz_service.create_quiz(db, workspace, body))


@router.get("/quizzes", response_model=list[QuizHistoryItem])
def quiz_history(
    limit: int = Query(50, ge=1, le=200), workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> list[QuizHistoryItem]:
    return quiz_service.history(db, workspace, limit)


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
def get_quiz(quiz_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> QuizOut:
    """Exam view of a quiz (no answers). Use /result after submission for answers and explanations."""
    return quiz_service.quiz_out(quiz_service.get_attempt(db, workspace, quiz_id))


@router.put("/quizzes/{quiz_id}/responses", response_model=QuizOut)
def save_responses(
    quiz_id: str, body: SaveResponses, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> QuizOut:
    """Autosave selected answers and review marks while the quiz is in progress."""
    return quiz_service.quiz_out(quiz_service.save_responses(db, workspace, quiz_id, body.responses))


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizResult)
def submit_quiz(
    quiz_id: str, body: SubmitRequest, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> QuizResult:
    """Submit once. Scoring uses the stored answer key; a second submission returns 409."""
    return quiz_service.quiz_result(quiz_service.submit(db, workspace, quiz_id, body.responses))


@router.get("/quizzes/{quiz_id}/result", response_model=QuizResult)
def quiz_result(
    quiz_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> QuizResult:
    return quiz_service.quiz_result(quiz_service.get_attempt(db, workspace, quiz_id))


@router.post("/quizzes/{quiz_id}/retry", response_model=QuizOut, status_code=201)
def retry_incorrect(
    quiz_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> QuizOut:
    """Start a new quiz containing the incorrect and unanswered questions of a submitted quiz."""
    limiter.check("quiz", workspace.id, get_settings().quizzes_per_hour)
    attempt = quiz_service.create_quiz(db, workspace, QuizCreate(mode="retry", source_attempt_id=quiz_id))
    return quiz_service.quiz_out(attempt)


@router.delete("/quizzes/{quiz_id}", status_code=204)
def delete_quiz(quiz_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> Response:
    quiz_service.delete_attempt(db, workspace, quiz_id)
    return Response(status_code=204)
