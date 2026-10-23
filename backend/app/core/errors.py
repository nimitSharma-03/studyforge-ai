"""Application error type and exception handlers that return safe, consistent JSON."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("studyforge")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


def _body(code: str, message: str, **extra) -> dict:
    return {"detail": message, "code": code, **extra}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, **exc.extra))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in err.get("loc", [])[1:]), "message": err.get("msg", "Invalid value")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content=_body("validation_error", "The request is invalid.", errors=errors)
        )

    @app.exception_handler(OperationalError)
    async def _db_unavailable(_request: Request, exc: OperationalError) -> JSONResponse:
        logger.error("database unavailable: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=503,
            content=_body("database_unavailable", "The database is temporarily unavailable. Please try again shortly."),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        ref = uuid.uuid4().hex[:8]
        logger.exception("database error ref=%s", ref)
        return JSONResponse(status_code=500, content=_body("database_error", "A database error occurred.", ref=ref))

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        ref = uuid.uuid4().hex[:8]
        logger.exception("unhandled error ref=%s", ref)
        return JSONResponse(status_code=500, content=_body("internal_error", "An unexpected error occurred.", ref=ref))
