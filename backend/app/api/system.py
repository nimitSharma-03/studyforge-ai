"""Health check and anonymous workspace endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import client_ip, get_workspace
from app.config import get_settings
from app.core.ratelimit import limiter
from app.core.security import hash_token, new_token
from app.db.session import engine, get_db
from app.models import Document, QuizAttempt, Workspace
from app.schemas import HealthOut, WorkspaceCreated, WorkspaceInfo

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(response: Response, db: Session = Depends(get_db)) -> HealthOut:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - report, don't raise, so the health check can describe the failure
        database = "error"
        response.status_code = 503
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        version=__version__,
        environment=settings.app_env,
        database=database,
        database_backend=engine.dialect.name,
        llm_enabled=settings.llm_enabled,
        max_upload_mb=settings.max_upload_mb,
    )


@router.post("/workspaces", response_model=WorkspaceCreated, status_code=201)
def create_workspace(request: Request, db: Session = Depends(get_db)) -> WorkspaceCreated:
    limiter.check("workspace", client_ip(request), get_settings().workspaces_per_hour_per_ip)
    token = new_token()
    workspace = Workspace(token_hash=hash_token(token))
    db.add(workspace)
    db.commit()
    return WorkspaceCreated(token=token, workspace_id=workspace.id, created_at=workspace.created_at)


@router.get("/workspaces/me", response_model=WorkspaceInfo)
def workspace_info(workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> WorkspaceInfo:
    settings = get_settings()
    docs = db.scalar(select(func.count()).select_from(Document).where(Document.workspace_id == workspace.id)) or 0
    attempts = (
        db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.workspace_id == workspace.id)) or 0
    )
    return WorkspaceInfo(
        workspace_id=workspace.id,
        created_at=workspace.created_at,
        document_count=docs,
        attempt_count=attempts,
        max_documents=settings.max_documents_per_workspace,
        max_upload_mb=settings.max_upload_mb,
        llm_enabled=settings.llm_enabled,
    )


@router.delete("/workspaces/me", status_code=204)
def delete_workspace(workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> Response:
    """Permanently delete the workspace and all documents, questions and quiz history in it."""
    from app.services.documents import delete_document

    for doc in list(workspace.documents):
        delete_document(db, workspace, doc)
    db.expire(workspace)
    db.delete(workspace)
    db.commit()
    return Response(status_code=204)
