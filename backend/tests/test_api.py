from __future__ import annotations

import json

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Chunk, Question, QuizAttempt, Topic


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["llm_enabled"] is False


def test_workspace_token_required(client):
    assert client.get("/api/documents").status_code == 401
    bad = client.get("/api/documents", headers={"X-Workspace-Token": "sfw_" + "x" * 40})
    assert bad.status_code == 401
    assert bad.json()["code"] == "workspace_invalid"


def test_workspace_info(client, headers):
    info = client.get("/api/workspaces/me", headers=headers).json()
    assert info["document_count"] == 0
    assert info["max_upload_mb"] == get_settings().max_upload_mb


# ------------------------------------------------------------------ uploads


def test_upload_each_format(client, headers, demo_pdf, demo_docx, demo_pptx):
    for name, data, unit in (
        ("n.pdf", demo_pdf, "page"),
        ("n.docx", demo_docx, "section"),
        ("n.pptx", demo_pptx, "slide"),
    ):
        r = client.post("/api/documents", headers=headers, files={"file": (name, data)})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "ready"
        assert body["unit_label"] == unit
        assert body["topic_count"] == 9
        assert body["question_count"] > 20
        assert body["preview"] and body["preview"][0]["location_start"] >= 1
    listing = client.get("/api/documents", headers=headers).json()
    assert len(listing) == 3


def test_unsupported_and_oversized_files(client, headers):
    r = client.post("/api/documents", headers=headers, files={"file": ("notes.txt", b"hello world")})
    assert r.status_code == 415
    assert r.json()["code"] == "unsupported_type"

    settings = get_settings()
    original = settings.max_upload_mb
    settings.max_upload_mb = 1
    try:
        r = client.post(
            "/api/documents", headers=headers, files={"file": ("big.pdf", b"%PDF-1.4" + b"0" * (1024 * 1024 + 10))}
        )
        assert r.status_code == 413
        assert r.json()["code"] == "file_too_large"
    finally:
        settings.max_upload_mb = original
    assert client.post("/api/documents", headers=headers, files={"file": ("e.pdf", b"")}).json()["code"] == "empty_file"


def test_corrupted_file_creates_failed_document(client, headers):
    r = client.post(
        "/api/documents", headers=headers, files={"file": ("broken.pdf", b"%PDF-1.4\n%garbage that is not a pdf")}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert body["error_code"] in {"corrupted", "insufficient_text"}
    assert body["error_message"]
    # A failed document cannot be studied.
    assert client.get(f"/api/documents/{body['id']}/topics", headers=headers).status_code == 409


def test_duplicate_upload_is_not_reprocessed(client, headers, demo_pdf):
    first = client.post("/api/documents", headers=headers, files={"file": ("a.pdf", demo_pdf)}).json()
    second = client.post("/api/documents", headers=headers, files={"file": ("copy.pdf", demo_pdf)}).json()
    assert second["id"] == first["id"]
    assert second["duplicate"] is True
    assert len(client.get("/api/documents", headers=headers).json()) == 1


def test_document_quota(client, headers, demo_docx):
    settings = get_settings()
    original = settings.max_documents_per_workspace
    settings.max_documents_per_workspace = 1
    try:
        client.post("/api/documents/sample", headers=headers)
        r = client.post("/api/documents", headers=headers, files={"file": ("n.docx", demo_docx)})
        assert r.status_code == 409
        assert r.json()["code"] == "quota_exceeded"
    finally:
        settings.max_documents_per_workspace = original


def test_upload_rate_limit(client, headers):
    settings = get_settings()
    original = settings.uploads_per_hour
    settings.uploads_per_hour = 2
    try:
        codes = [client.post("/api/documents/sample", headers=headers).status_code for _ in range(3)]
        assert codes == [201, 201, 429]
    finally:
        settings.uploads_per_hour = original


# ------------------------------------------------------------------ documents and topics


def test_rename_content_and_topics(client, headers, ready_doc):
    doc_id = ready_doc["id"]
    r = client.patch(f"/api/documents/{doc_id}", headers=headers, json={"name": "  NLP   Unit 1 "})
    assert r.json()["name"] == "NLP Unit 1"
    page = client.get(f"/api/documents/{doc_id}/content?offset=0&limit=4", headers=headers).json()
    assert page["total"] == ready_doc["chunk_count"]
    assert len(page["items"]) == 4
    topics = client.get(f"/api/documents/{doc_id}/topics", headers=headers).json()
    assert [t["position"] for t in topics] == list(range(len(topics)))
    detail = client.get(f"/api/topics/{topics[1]['id']}", headers=headers).json()
    assert detail["title"] == "Text Preprocessing"
    assert detail["prev_topic_id"] == topics[0]["id"] and detail["next_topic_id"] == topics[2]["id"]
    assert detail["guide"]["definitions"]
    assert detail["chunks"] and all(c["topic_id"] == topics[1]["id"] for c in detail["chunks"])


def test_ask_endpoint(client, headers, ready_doc):
    r = client.post(
        f"/api/documents/{ready_doc['id']}/ask", headers=headers, json={"question": "Why can accuracy be misleading?"}
    ).json()
    assert r["verdict"] in {"supported", "partial"}
    assert "imbalanced" in r["answer"][0]["text"]
    assert r["passages"][0]["location_type"] == "page"
    none = client.post(
        f"/api/documents/{ready_doc['id']}/ask",
        headers=headers,
        json={"question": "What is the boiling point of mercury?"},
    ).json()
    assert none["verdict"] == "insufficient"


def test_llm_endpoint_reports_unavailable(client, headers, ready_doc):
    r = client.post(f"/api/topics/{ready_doc['topics'][0]['id']}/llm-explanation", headers=headers)
    assert r.status_code == 503
    assert r.json()["code"] == "llm_unavailable"


def test_cross_workspace_access_is_denied(client, headers, ready_doc):
    other = {"X-Workspace-Token": client.post("/api/workspaces").json()["token"]}
    doc_id = ready_doc["id"]
    topic_id = ready_doc["topics"][0]["id"]
    assert client.get(f"/api/documents/{doc_id}", headers=other).status_code == 404
    assert client.get(f"/api/topics/{topic_id}", headers=other).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=other).status_code == 404
    assert client.get(f"/api/questions?document_id={doc_id}", headers=other).status_code == 404
    assert (
        client.post("/api/quizzes", headers=other, json={"mode": "end_sem", "document_ids": [doc_id]}).status_code
        == 404
    )
    quiz = client.post("/api/quizzes", headers=headers, json={"mode": "end_sem", "document_ids": [doc_id]}).json()
    assert client.get(f"/api/quizzes/{quiz['id']}", headers=other).status_code == 404
    assert client.post(f"/api/quizzes/{quiz['id']}/submit", headers=other, json={"responses": []}).status_code == 404
    assert client.get(f"/api/exports/documents/{doc_id}/notes", headers=other).status_code == 404


def test_delete_document_cleans_up(client, headers, ready_doc):
    doc_id = ready_doc["id"]
    quiz = client.post("/api/quizzes", headers=headers, json={"mode": "end_sem", "document_ids": [doc_id]}).json()
    impact = client.get(f"/api/documents/{doc_id}/delete-impact", headers=headers).json()
    assert impact["quiz_attempts"] == 1
    assert client.delete(f"/api/documents/{doc_id}", headers=headers).status_code == 204
    assert client.get(f"/api/documents/{doc_id}", headers=headers).status_code == 404
    with SessionLocal() as db:
        assert db.query(Topic).filter_by(document_id=doc_id).count() == 0
        assert db.query(Chunk).filter_by(document_id=doc_id).count() == 0
        assert db.query(Question).filter_by(document_id=doc_id).count() == 0
        assert db.get(QuizAttempt, quiz["id"]) is None


def test_delete_workspace_removes_everything(client, headers, ready_doc):
    assert client.delete("/api/workspaces/me", headers=headers).status_code == 204
    assert client.get("/api/documents", headers=headers).status_code == 401
    with SessionLocal() as db:
        assert db.query(Topic).filter_by(document_id=ready_doc["id"]).count() == 0


# ------------------------------------------------------------------ question bank


def test_question_bank_filters(client, headers, ready_doc):
    doc_id = ready_doc["id"]
    page = client.get(f"/api/questions?document_id={doc_id}&question_type=mcq&difficulty=easy", headers=headers).json()
    assert page["total"] > 0
    assert all(q["question_type"] == "mcq" and q["difficulty"] == "easy" for q in page["items"])
    assert set(page["counts"]["question_type"]) == {"mcq", "short_answer", "long_answer"}
    topic_id = ready_doc["topics"][2]["id"]
    page = client.get(f"/api/questions?document_id={doc_id}&topic_id={topic_id}", headers=headers).json()
    assert all(q["topic_id"] == topic_id and q["topic_title"] == "Tokenization" for q in page["items"])


def test_generate_question_set(client, headers, ready_doc):
    body = {"document_id": ready_doc["id"], "question_types": ["mcq"], "count": 5, "seed": 1}
    r = client.post("/api/questions/generate", headers=headers, json=body).json()
    assert len(r["questions"]) == 5
    assert r["available"] >= 5
    body = {
        "document_id": ready_doc["id"],
        "topic_ids": [ready_doc["topics"][2]["id"]],
        "question_types": ["long_answer"],
        "count": 50,
    }
    r = client.post("/api/questions/generate", headers=headers, json=body).json()
    assert r["available"] == len(r["questions"]) < 50
    assert "smaller than requested" in r["message"]


# ------------------------------------------------------------------ exports


def test_exports(client, headers, ready_doc):
    doc_id = ready_doc["id"]
    md = client.get(f"/api/exports/documents/{doc_id}/notes?format=md&mode=concise", headers=headers)
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert 'filename="foundations-of-nlp-demo-revision-concise.md"' in md.headers["content-disposition"]
    assert "## 3. Tokenization" in md.text and "Page " in md.text
    txt = client.get(f"/api/exports/documents/{doc_id}/notes?format=txt", headers=headers)
    assert "TOKENIZATION" not in txt.text and "Tokenization" in txt.text and "**" not in txt.text
    pdf = client.get(f"/api/exports/documents/{doc_id}/questions?format=pdf&answers=true", headers=headers)
    assert pdf.content.startswith(b"%PDF")
    qmd = client.get(f"/api/exports/documents/{doc_id}/questions?format=md&question_type=mcq", headers=headers).text
    assert "## Answer key" in qmd and "(A)" in qmd
    no_key = client.get(f"/api/exports/documents/{doc_id}/questions?format=md&answers=false", headers=headers).text
    assert "Answer key" not in no_key
    assert client.get(f"/api/exports/documents/{doc_id}/notes?format=exe", headers=headers).status_code == 422


def test_error_responses_have_codes(client, headers):
    r = client.get("/api/documents/does-not-exist", headers=headers)
    assert r.status_code == 404 and r.json() == {"detail": "Document not found.", "code": "document_not_found"}
    r = client.post("/api/quizzes", headers=headers, json={"mode": "nonsense"})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert json.loads(r.text)["errors"]
