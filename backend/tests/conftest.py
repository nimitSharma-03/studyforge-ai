from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="studyforge-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["OLLAMA_URL"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.ratelimit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.sample_data.demo_content import NOTICE, SECTIONS, TITLE  # noqa: E402
from app.utils.sample_docs import build_docx, build_pdf, build_pptx  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()
    yield


@pytest.fixture
def headers(client) -> dict[str, str]:
    response = client.post("/api/workspaces")
    assert response.status_code == 201
    return {"X-Workspace-Token": response.json()["token"]}


@pytest.fixture(scope="session")
def demo_pdf() -> bytes:
    return build_pdf(TITLE, SECTIONS, NOTICE)


@pytest.fixture(scope="session")
def demo_docx() -> bytes:
    return build_docx(TITLE, SECTIONS, NOTICE)


@pytest.fixture(scope="session")
def demo_pptx() -> bytes:
    return build_pptx(TITLE, SECTIONS, NOTICE)


@pytest.fixture
def ready_doc(client, headers) -> dict:
    response = client.post("/api/documents/sample", headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    return body
