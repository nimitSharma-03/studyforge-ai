"""Shared API dependencies."""

from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_token, looks_like_token
from app.db.session import get_db
from app.models import Workspace, utcnow

TOKEN_HEADER = "X-Workspace-Token"


def get_workspace(
    db: Session = Depends(get_db),
    x_workspace_token: str | None = Header(default=None, alias=TOKEN_HEADER),
) -> Workspace:
    if not looks_like_token(x_workspace_token):
        raise AppError(401, "workspace_required", "A valid workspace token is required.")
    workspace = db.scalar(select(Workspace).where(Workspace.token_hash == hash_token(x_workspace_token)))
    if workspace is None:
        raise AppError(401, "workspace_invalid", "This workspace no longer exists. A new one will be created.")
    now = utcnow()
    last = workspace.last_seen_at
    if last is None or (now - (last if last.tzinfo else last.replace(tzinfo=now.tzinfo))) > timedelta(minutes=10):
        workspace.last_seen_at = now
        db.commit()
    return workspace


def client_ip(request: Request) -> str:
    # Render terminates TLS at a proxy and forwards the client address in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
