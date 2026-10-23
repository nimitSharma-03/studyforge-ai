"""FastAPI application entry point."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app import __version__
from app.api import documents, progress, questions, quizzes, system
from app.api.deps import TOKEN_HEADER
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.db.session import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("studyforge")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    init_db()
    if settings.is_production and settings.database_url.startswith("sqlite"):
        logger.warning("Production is using SQLite; data will not survive restarts. Set DATABASE_URL to PostgreSQL.")
    logger.info("StudyForge API %s started (env=%s, docs=%s)", __version__, settings.app_env, settings.docs_enabled)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="StudyForge AI API",
        version=__version__,
        description="Document-grounded NLP study platform: extraction, topics, learning guides, questions and quizzes.",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", TOKEN_HEADER],
        expose_headers=["Content-Disposition"],
        max_age=600,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        # Paths and status only: request bodies (document text, answers) are never logged.
        logger.info(
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    register_error_handlers(app)
    for router in (system.router, documents.router, questions.router, quizzes.router, progress.router):
        app.include_router(router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": "StudyForge AI API", "version": __version__, "health": "/api/health"}

    return app


app = create_app()
