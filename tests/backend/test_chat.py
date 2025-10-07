from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from backend.app.main import create_app


def setup_module(module):
    base_path = Path(__file__).resolve().parents[1]
    data_txt = (base_path / ".." / "data" / "txt").resolve()
    data_txt.mkdir(parents=True, exist_ok=True)
    (data_txt / "sample.txt").write_text("Sample knowledge base", encoding="utf-8")


def teardown_module(module):
    base_path = Path(__file__).resolve().parents[1]
    data_txt = (base_path / ".." / "data" / "txt").resolve()
    sample = data_txt / "sample.txt"
    if sample.exists():
        sample.unlink()


def test_health_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ingest_and_chat_streaming():
    app = create_app()
    client = TestClient(app)

    ingest_response = client.post("/chat/ingest")
    assert ingest_response.status_code == 200
    assert ingest_response.json()["documents_ingested"] >= 1

    with client.stream("POST", "/chat/stream", json={"prompt": "Hello"}) as stream:
        chunks = list(stream.iter_text())
    assert any("Hello" in chunk for chunk in chunks)
    assert any("sample.txt" in chunk or "Sample" in chunk for chunk in chunks)
