from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat
from .services.graphrag import GraphRAGChatEngine
from .services.ingestion import DataDirectoryIngestor

LOGGER = logging.getLogger(__name__)


def create_app(*, base_path: Path | None = None, engine: GraphRAGChatEngine | None = None) -> FastAPI:
    """Application factory used by both production and tests."""

    resolved_base = base_path or Path(__file__).resolve().parents[2]
    app = FastAPI(title="GraphRAG Ollama Demo")

    app.state.engine = engine or GraphRAGChatEngine()
    app.state.ingestor = DataDirectoryIngestor(base_path=resolved_base)

    app.include_router(chat.router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check() -> dict:
        return {"status": "ok"}

    LOGGER.info("FastAPI application initialised")

    return app


app = create_app()
