from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat
from .services.graphrag import GraphRAGChatEngine
from .services.ingestion import DataDirectoryIngestor

LOGGER = logging.getLogger(__name__)


def create_app() -> FastAPI:
    base_path = Path(__file__).resolve().parents[2]
    app = FastAPI(title="GraphRAG Ollama Demo")

    engine = GraphRAGChatEngine()
    ingestor = DataDirectoryIngestor(base_path=base_path)

    chat.router.state.engine = engine  # type: ignore[attr-defined]
    chat.router.state.ingestor = ingestor  # type: ignore[attr-defined]

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
