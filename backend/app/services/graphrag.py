"""GraphRAG service wiring with a production-ready backend and stub fallback."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Dict, Iterable, List, Optional

from dotenv import load_dotenv

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - exercised in integration environments
    from graphrag_sdk import KnowledgeGraph, Ontology
    from graphrag_sdk.model_config import KnowledgeGraphModelConfig
    from graphrag_sdk.models.litellm import LiteModel
    from graphrag_sdk.models.ollama import OllamaGenerativeModel
    from graphrag_sdk.source import Source_FromRawText

    HAS_GRAPH_BACKEND = True
    GRAPH_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - when optional deps missing
    KnowledgeGraph = None  # type: ignore[assignment]
    Ontology = None  # type: ignore[assignment]
    KnowledgeGraphModelConfig = None  # type: ignore[assignment]
    LiteModel = None  # type: ignore[assignment]
    OllamaGenerativeModel = None  # type: ignore[assignment]
    Source_FromRawText = None  # type: ignore[assignment]

    HAS_GRAPH_BACKEND = False
    GRAPH_IMPORT_ERROR = exc


class GraphRAGConfigurationError(RuntimeError):
    """Raised when the production GraphRAG backend cannot be initialised."""


@dataclass
class Document:
    """Simple representation of an ingested document."""

    name: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class GraphRAGConfig:
    """Configuration values required for a GraphRAG service instance."""

    base_path: Path
    kg_name: str
    ontology_path: Path
    extraction_model: str
    cypher_model: Optional[str]
    ollama_model: str
    ollama_base_url: str
    falkordb_host: str
    falkordb_port: int
    falkordb_username: Optional[str]
    falkordb_password: Optional[str]
    auto_refresh_ontology: bool
    reset_before_ingest: bool
    force_stub: bool

    @staticmethod
    def _env_bool(value: Optional[str], default: bool = False) -> bool:
        if value is None:
            return default
        return value.lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_env(cls, base_path: Path) -> "GraphRAGConfig":
        """Load configuration from the environment and optional .env file."""

        env_path = base_path / ".env"
        load_dotenv(env_path, override=False)
        load_dotenv(override=False)

        def env(name: str, default: Optional[str] = None) -> Optional[str]:
            return os.getenv(name, default)

        def env_int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except ValueError:
                LOGGER.warning("Invalid integer for %s=%s, falling back to %d", name, raw, default)
                return default

        def env_bool(name: str, default: bool = False) -> bool:
            return cls._env_bool(os.getenv(name), default)

        ontology_location = env("GRAPHRAG_ONTOLOGY_PATH")
        ontology_path = Path(ontology_location) if ontology_location else base_path / "data" / "ontology" / "ontology.json"

        return cls(
            base_path=base_path,
            kg_name=env("GRAPHRAG_KG_NAME", "graphrag_demo") or "graphrag_demo",
            ontology_path=ontology_path,
            extraction_model=env("GRAPHRAG_EXTRACTION_MODEL", "openai/gpt-4.1") or "openai/gpt-4.1",
            cypher_model=env("GRAPHRAG_CYPHER_MODEL"),
            ollama_model=env("OLLAMA_MODEL", "llama3.1:8b") or "llama3.1:8b",
            ollama_base_url=env("OLLAMA_BASE_URL", "http://localhost:11434") or "http://localhost:11434",
            falkordb_host=env("FALKORDB_HOST", "127.0.0.1") or "127.0.0.1",
            falkordb_port=env_int("FALKORDB_PORT", 6379),
            falkordb_username=env("FALKORDB_USERNAME"),
            falkordb_password=env("FALKORDB_PASSWORD"),
            auto_refresh_ontology=env_bool("GRAPHRAG_AUTO_REFRESH_ONTOLOGY", True),
            reset_before_ingest=env_bool("GRAPHRAG_RESET_BEFORE_INGEST", False),
            force_stub=env_bool("GRAPHRAG_USE_STUB", False),
        )


class StubGraphRAGChatEngine:
    """Tiny in-memory chat engine that mimics GraphRAG behaviour for tests."""

    def __init__(self) -> None:
        self._documents: Dict[str, Document] = {}
        self._chat_history: List[Dict[str, str]] = []

    def ingest(self, documents: Iterable[Document]) -> Dict[str, int]:
        """Add the provided documents to the in-memory store."""

        added = 0
        for doc in documents:
            self._documents[doc.name] = doc
            added += 1
        return {"documents_ingested": added, "total_documents": len(self._documents)}

    def get_documents(self) -> List[Document]:
        return list(self._documents.values())

    async def stream_chat(self, prompt: str) -> AsyncGenerator[str, None]:
        """Generate a deterministic response for the supplied prompt."""

        self._chat_history.append({"role": "user", "content": prompt})

        highlights = self._build_highlights(prompt)
        answer = self._render_answer(prompt, highlights)
        self._chat_history.append({"role": "assistant", "content": answer})

        for chunk in answer.split():
            await asyncio.sleep(0)
            yield chunk + " "

    def reset(self) -> None:
        self._documents.clear()
        self._chat_history.clear()

    # Internal helpers -------------------------------------------------
    def _build_highlights(self, prompt: str) -> List[tuple[Document, int]]:
        """Return documents ranked by lexical overlap with the prompt."""

        tokens = {token.lower() for token in prompt.split() if token}
        if not tokens or not self._documents:
            return []

        ranked: List[tuple[Document, int]] = []
        for document in self._documents.values():
            score = sum(1 for token in tokens if token in document.content.lower())
            if score:
                ranked.append((document, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:3]

    def _render_answer(self, prompt: str, highlights: List[tuple[Document, int]]) -> str:
        if not self._documents:
            return "No knowledge available yet. Please ingest documents and try again."

        if not highlights:
            available = ", ".join(doc.name for doc in self._documents.values())
            return f"No direct match found for '{prompt}'. Available documents: {available}."

        summary_lines = []
        for document, score in highlights:
            snippet = document.content.strip().splitlines()[0:2]
            excerpt = " / ".join(part.strip() for part in snippet if part.strip())
            summary_lines.append(f"{document.name} (score {score}): {excerpt}")

        summary = " | ".join(summary_lines)
        return f"Prompt: {prompt}\nTop sources: {summary}"


class GraphRAGService:
    """High-level facade wiring GraphRAG-SDK with Ollama for production use."""

    def __init__(self, config: GraphRAGConfig, *, force_stub: Optional[bool] = None) -> None:
        self.config = config
        self.config.ontology_path.parent.mkdir(parents=True, exist_ok=True)

        self._documents: Dict[str, Document] = {}
        self._last_ingest_summary: Dict[str, object] = {}
        self._knowledge_graph: Optional[KnowledgeGraph] = None
        self._chat_session = None
        self._model_config: Optional[KnowledgeGraphModelConfig] = None
        self._ontology: Optional[Ontology] = None

        self._using_stub = force_stub if force_stub is not None else config.force_stub

        if not self._using_stub and not HAS_GRAPH_BACKEND:
            LOGGER.warning("graphrag_sdk not available (%s); using stub backend", GRAPH_IMPORT_ERROR)
            self._using_stub = True

        if self._using_stub:
            self._engine = StubGraphRAGChatEngine()
            return

        try:
            self._initialise_real_backend()
        except GraphRAGConfigurationError as exc:
            LOGGER.warning("GraphRAG initialisation failed (%s); falling back to stub backend", exc)
            self._engine = StubGraphRAGChatEngine()
            self._using_stub = True

    # ------------------------------------------------------------------
    @property
    def using_stub(self) -> bool:
        return self._using_stub

    def ingest(self, documents: Iterable[Document]) -> Dict[str, object]:
        documents = list(documents)

        if self._using_stub:
            summary = self._engine.ingest(documents)
            summary.update(
                {
                    "using_stub": True,
                    "graph_name": None,
                    "ontology_path": None,
                    "ontology_refreshed": False,
                }
            )
            summary["document_names"] = [doc.name for doc in documents]
            self._last_ingest_summary = summary
            return summary

        if self._knowledge_graph is None or self._model_config is None:
            raise GraphRAGConfigurationError("Knowledge graph backend is not available")

        if not documents:
            summary = {
                "documents_ingested": 0,
                "total_documents": len(self._documents),
                "graph_name": self.config.kg_name,
                "ontology_path": str(self.config.ontology_path),
                "ontology_refreshed": False,
                "using_stub": False,
                "document_names": [],
            }
            self._last_ingest_summary = summary
            return summary

        if self.config.reset_before_ingest:
            self.reset()

        sources = [self._build_source(doc) for doc in documents]

        ontology_refreshed = False
        if self.config.auto_refresh_ontology or self._ontology is None:
            self._ontology = self._build_ontology(sources)
            self._knowledge_graph.ontology = self._ontology
            ontology_refreshed = True

        try:
            self._knowledge_graph.process_sources(sources, hide_progress=True)
        except Exception as exc:  # pragma: no cover - depends on external services
            raise GraphRAGConfigurationError(f"Failed to process sources: {exc}") from exc

        self._documents = {doc.name: doc for doc in documents}
        self._chat_session = self._knowledge_graph.chat_session()

        summary = {
            "documents_ingested": len(documents),
            "total_documents": len(self._documents),
            "graph_name": self.config.kg_name,
            "ontology_path": str(self.config.ontology_path),
            "ontology_refreshed": ontology_refreshed,
            "using_stub": False,
            "document_names": [doc.name for doc in documents],
        }
        self._last_ingest_summary = summary
        return summary

    def get_documents(self) -> List[Document]:
        if self._using_stub:
            return self._engine.get_documents()
        return list(self._documents.values())

    async def stream_chat(self, prompt: str) -> AsyncGenerator[str, None]:
        if self._using_stub:
            async for chunk in self._engine.stream_chat(prompt):
                yield chunk
            return

        if self._chat_session is None:
            raise GraphRAGConfigurationError("No active chat session. Ingest documents first.")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        error: List[Exception] = []

        def worker() -> None:
            try:
                for chunk in self._chat_session.send_message_stream(prompt):  # type: ignore[attr-defined]
                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
            except Exception as exc:  # pragma: no cover - relies on backend availability
                error.append(exc)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

        threading.Thread(target=worker, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        if error:
            raise GraphRAGConfigurationError(f"GraphRAG streaming failed: {error[0]}") from error[0]

    def reset(self) -> None:
        if self._using_stub:
            self._engine.reset()
            return

        if self._knowledge_graph is not None:
            try:
                self._knowledge_graph.delete()
            except Exception as exc:  # pragma: no cover - relies on backend availability
                LOGGER.warning("Failed to delete knowledge graph: %s", exc)

        self._initialise_real_backend()

    # Internal helpers -------------------------------------------------
    def _initialise_real_backend(self) -> None:
        if not HAS_GRAPH_BACKEND:
            raise GraphRAGConfigurationError("graphrag_sdk is not installed")

        try:
            extract_model = LiteModel(model_name=self.config.extraction_model)
            cypher_model_name = self.config.cypher_model or self.config.extraction_model
            cypher_model = LiteModel(model_name=cypher_model_name)
        except ValueError as exc:  # pragma: no cover - depends on env configuration
            raise GraphRAGConfigurationError(f"LiteLLM provider configuration error: {exc}") from exc

        try:
            qa_model = OllamaGenerativeModel(model_name=self.config.ollama_model, api_base=self.config.ollama_base_url)
        except Exception as exc:  # pragma: no cover - depends on local Ollama
            raise GraphRAGConfigurationError(f"Ollama configuration error: {exc}") from exc

        self._model_config = KnowledgeGraphModelConfig(
            extract_data=extract_model,
            cypher_generation=cypher_model,
            qa=qa_model,
        )

        ontology = self._load_existing_ontology()

        try:
            self._knowledge_graph = KnowledgeGraph(
                name=self.config.kg_name,
                model_config=self._model_config,
                ontology=ontology,
                host=self.config.falkordb_host,
                port=self.config.falkordb_port,
                username=self.config.falkordb_username,
                password=self.config.falkordb_password,
            )
        except Exception as exc:  # pragma: no cover - depends on FalkorDB availability
            raise GraphRAGConfigurationError(
                f"Failed to connect to FalkorDB at {self.config.falkordb_host}:{self.config.falkordb_port}: {exc}"
            ) from exc

        self._ontology = self._knowledge_graph.ontology or ontology
        self._chat_session = None
        self._documents.clear()

    def _build_source(self, document: Document):
        instruction = f"Source: {document.name}"
        return Source_FromRawText(document.content, instruction=instruction)

    def _build_ontology(self, sources):
        if self._model_config is None:
            raise GraphRAGConfigurationError("Model configuration not initialised")

        try:
            ontology = Ontology.from_sources(sources=sources, model=self._model_config.extract_data, hide_progress=True)
        except Exception as exc:  # pragma: no cover - depends on model behaviour
            raise GraphRAGConfigurationError(f"Failed to build ontology: {exc}") from exc

        data = json.dumps(ontology.to_json(), indent=2)
        self.config.ontology_path.write_text(data, encoding="utf-8")
        return ontology

    def _load_existing_ontology(self) -> Optional[Ontology]:
        if not self.config.ontology_path.exists():
            return None
        try:
            raw = self.config.ontology_path.read_text(encoding="utf-8")
            if not raw.strip():
                return None
            payload = json.loads(raw)
            return Ontology.from_json(payload)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("Failed to load ontology from %s: %s", self.config.ontology_path, exc)
            return None


__all__ = [
    "Document",
    "GraphRAGConfig",
    "GraphRAGConfigurationError",
    "GraphRAGService",
    "StubGraphRAGChatEngine",
]
