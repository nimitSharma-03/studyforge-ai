"""Document upload, listing, content and topic endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_workspace
from app.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.db.session import get_db
from app.models import Chunk, Document, Question, Topic, Workspace
from app.nlp import llm
from app.nlp.retrieval import Passage, PassageIndex, answer_question, index_cache
from app.schemas import (
    AskRequest,
    AskResponse,
    ChunkOut,
    ContentPage,
    DeleteImpact,
    DocumentDetail,
    DocumentSummary,
    LLMExplanation,
    RenameRequest,
    TopicDetail,
    TopicSummary,
)
from app.services import documents as doc_service

router = APIRouter(tags=["documents"])


def _topic_summaries(db: Session, doc: Document) -> list[TopicSummary]:
    counts = dict(
        db.execute(
            select(Question.topic_id, func.count()).where(Question.document_id == doc.id).group_by(Question.topic_id)
        ).all()
    )
    return [
        TopicSummary.model_validate(t).model_copy(update={"question_count": counts.get(t.id, 0)}) for t in doc.topics
    ]


def _detail(db: Session, doc: Document, duplicate: bool = False) -> DocumentDetail:
    preview = db.scalars(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.position).limit(3)).all()
    return DocumentDetail.model_validate(doc).model_copy(
        update={
            "topics": _topic_summaries(db, doc) if doc.status == "ready" else [],
            "preview": [ChunkOut.model_validate(c) for c in preview],
            "duplicate": duplicate,
        }
    )


def _read_upload(request: Request, file: UploadFile) -> bytes:
    limit = get_settings().max_upload_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 1024 * 64:
        raise AppError(413, "file_too_large", f"Files must be {get_settings().max_upload_mb} MB or smaller.")
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise AppError(413, "file_too_large", f"Files must be {get_settings().max_upload_mb} MB or smaller.")
    return data


@router.post("/documents", response_model=DocumentDetail, status_code=201)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> DocumentDetail:
    """Upload a PDF, DOCX or PPTX file. Processing runs synchronously; the response reports the real outcome."""
    limiter.check("upload", workspace.id, get_settings().uploads_per_hour)
    data = _read_upload(request, file)
    doc, duplicate = doc_service.ingest(db, workspace, file.filename or "upload", data)
    return _detail(db, doc, duplicate)


@router.post("/documents/sample", response_model=DocumentDetail, status_code=201)
def load_sample(workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> DocumentDetail:
    """Add the bundled synthetic demo notes ("Foundations of NLP") to this workspace."""
    from app.sample_data import demo_pdf_bytes

    limiter.check("upload", workspace.id, get_settings().uploads_per_hour)
    doc, duplicate = doc_service.ingest(
        db, workspace, "Foundations of NLP (demo).pdf", demo_pdf_bytes(), is_sample=True
    )
    return _detail(db, doc, duplicate)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)) -> list[Document]:
    return list(
        db.scalars(select(Document).where(Document.workspace_id == workspace.id).order_by(Document.created_at.desc()))
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> DocumentDetail:
    return _detail(db, doc_service.get_document(db, workspace, document_id))


@router.patch("/documents/{document_id}", response_model=DocumentSummary)
def rename_document(
    document_id: str, body: RenameRequest, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> Document:
    doc = doc_service.get_document(db, workspace, document_id)
    name = " ".join(body.name.split())
    if not name:
        raise AppError(422, "invalid_name", "The name cannot be empty.")
    doc.name = name[:200]
    db.commit()
    return doc


@router.get("/documents/{document_id}/delete-impact", response_model=DeleteImpact)
def delete_impact(
    document_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> DeleteImpact:
    doc = doc_service.get_document(db, workspace, document_id)
    attempts = doc_service.attempts_using_document(db, workspace, doc.id)
    return DeleteImpact(
        document_id=doc.id, topics=doc.topic_count, questions=doc.question_count, quiz_attempts=len(attempts)
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> Response:
    doc = doc_service.get_document(db, workspace, document_id)
    doc_service.delete_document(db, workspace, doc)
    return Response(status_code=204)


@router.get("/documents/{document_id}/content", response_model=ContentPage)
def document_content(
    document_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    topic_id: int | None = None,
    workspace: Workspace = Depends(get_workspace),
    db: Session = Depends(get_db),
) -> ContentPage:
    doc = doc_service.get_document(db, workspace, document_id)
    stmt = select(Chunk).where(Chunk.document_id == doc.id)
    count_stmt = select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
    if topic_id is not None:
        stmt = stmt.where(Chunk.topic_id == topic_id)
        count_stmt = count_stmt.where(Chunk.topic_id == topic_id)
    total = db.scalar(count_stmt) or 0
    items = db.scalars(stmt.order_by(Chunk.position).offset(offset).limit(limit)).all()
    return ContentPage(items=[ChunkOut.model_validate(c) for c in items], total=total, offset=offset, limit=limit)


@router.get("/documents/{document_id}/topics", response_model=list[TopicSummary])
def list_topics(
    document_id: str, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> list[TopicSummary]:
    doc = doc_service.get_ready_document(db, workspace, document_id)
    return _topic_summaries(db, doc)


def _get_topic(db: Session, workspace: Workspace, topic_id: int) -> tuple[Topic, Document]:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise AppError(404, "topic_not_found", "Topic not found.")
    doc = db.get(Document, topic.document_id)
    if doc is None or doc.workspace_id != workspace.id:
        raise AppError(404, "topic_not_found", "Topic not found.")
    return topic, doc


@router.get("/topics/{topic_id}", response_model=TopicDetail)
def get_topic(
    topic_id: int, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> TopicDetail:
    topic, doc = _get_topic(db, workspace, topic_id)
    summaries = _topic_summaries(db, doc)
    ids = [t.id for t in summaries]
    i = ids.index(topic.id)
    summary = summaries[i]
    chunks = db.scalars(select(Chunk).where(Chunk.topic_id == topic.id).order_by(Chunk.position)).all()
    return TopicDetail(
        **summary.model_dump(),
        document_name=doc.name,
        unit_label=doc.unit_label,
        guide=topic.guide or {},
        chunks=[ChunkOut.model_validate(c) for c in chunks],
        prev_topic_id=ids[i - 1] if i > 0 else None,
        next_topic_id=ids[i + 1] if i + 1 < len(ids) else None,
    )


def _index_for(db: Session, doc: Document) -> PassageIndex:
    def build() -> PassageIndex:
        chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.position)).all()
        return PassageIndex(
            [
                Passage(c.id, c.text, c.heading, c.topic_id, c.location_type, c.location_start, c.location_end)
                for c in chunks
            ]
        )

    return index_cache.get(f"{doc.id}:{doc.chunk_count}", build)


@router.post("/documents/{document_id}/ask", response_model=AskResponse)
def ask(
    document_id: str, body: AskRequest, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> dict:
    """Answer a question with sentences retrieved from the document (TF-IDF + cosine similarity)."""
    doc = doc_service.get_ready_document(db, workspace, document_id)
    if body.topic_id is not None:
        _get_topic(db, workspace, body.topic_id)
    definitions = [
        {**d, "topic_id": t.id, "location_type": doc.unit_label}
        for t in doc.topics
        for d in (t.guide or {}).get("definitions", [])
    ]
    return answer_question(body.question, _index_for(db, doc), definitions, topic_id=body.topic_id)


@router.post("/topics/{topic_id}/llm-explanation", response_model=LLMExplanation)
def llm_explanation(
    topic_id: int, workspace: Workspace = Depends(get_workspace), db: Session = Depends(get_db)
) -> LLMExplanation:
    """Optional: ask a locally configured Ollama model to explain a topic using only its source passages."""
    topic, _doc = _get_topic(db, workspace, topic_id)
    limiter.check("llm", workspace.id, 30)
    chunks = db.scalars(select(Chunk).where(Chunk.topic_id == topic.id).order_by(Chunk.position).limit(6)).all()
    try:
        text, model = llm.explain_topic(topic.title, [c.text for c in chunks])
    except llm.LLMUnavailable as exc:
        raise AppError(503, "llm_unavailable", str(exc)) from exc
    return LLMExplanation(topic_id=topic.id, model=model, text=text, passages_used=len(chunks))
