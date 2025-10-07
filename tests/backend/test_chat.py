from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture()
def client(tmp_path):
    data_root = tmp_path / "data" / "txt"
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "sample.txt").write_text("Sample knowledge base", encoding="utf-8")

    app = create_app(base_path=tmp_path)
    return TestClient(app)


def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ingest_and_chat_streaming(client: TestClient):
    ingest_response = client.post("/chat/ingest")
    assert ingest_response.status_code == 200
    assert ingest_response.json()["documents_ingested"] >= 1

    with client.stream("POST", "/chat/stream", json={"prompt": "Hello"}) as stream:
        chunks = list(stream.iter_text())
    assert any("Hello" in chunk for chunk in chunks)
    assert any("sample.txt" in chunk or "Sample" in chunk for chunk in chunks)


def test_upload_and_list_documents(client: TestClient, tmp_path):
    upload_response = client.post("/chat/upload", files={"file": ("upload.txt", b"Uploaded content", "text/plain")})
    assert upload_response.status_code == 200
    stored_at = upload_response.json()["stored_at"]
    stored_path = tmp_path / "data" / "txt" / "upload.txt"
    assert stored_at == str(stored_path)
    assert stored_path.exists()
    assert stored_path.read_text(encoding="utf-8") == "Uploaded content"

    ingest_response = client.post("/chat/ingest")
    assert ingest_response.status_code == 200
    assert "upload.txt" in ingest_response.json()["document_names"]

    documents_response = client.get("/chat/documents")
    assert documents_response.status_code == 200
    assert "upload.txt" in documents_response.json()["documents"]
