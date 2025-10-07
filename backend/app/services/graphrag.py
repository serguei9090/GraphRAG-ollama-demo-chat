"""Utility classes that emulate a GraphRAG + Ollama pipeline.

These classes provide a lightweight shim that mimics the interface of a
GraphRAG backed conversational agent so that the FastAPI application can run
without the heavy dependencies.  The implementation keeps the ingested
content in memory and synthesises deterministic responses for tests.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List


@dataclass
class Document:
    """Simple representation of an ingested document."""

    name: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


class GraphRAGChatEngine:
    """Tiny in-memory chat engine that mimics GraphRAG behaviour."""

    def __init__(self) -> None:
        self._documents: List[Document] = []
        self._chat_history: List[Dict[str, str]] = []

    def ingest(self, documents: List[Document]) -> Dict[str, int]:
        """Add the provided documents to the in-memory store."""

        self._documents.extend(documents)
        return {"documents_ingested": len(documents), "total_documents": len(self._documents)}

    def get_documents(self) -> List[Document]:
        return list(self._documents)

    async def stream_chat(self, prompt: str) -> AsyncGenerator[str, None]:
        """Generate a deterministic response for the supplied prompt."""

        self._chat_history.append({"role": "user", "content": prompt})

        summary = " ".join(doc.name for doc in self._documents) or "no documents"
        answer = f"Response based on {summary}: {prompt}"
        self._chat_history.append({"role": "assistant", "content": answer})

        for chunk in answer.split():
            await asyncio.sleep(0)  # allow the event loop to switch context
            yield chunk + " "

    def reset(self) -> None:
        self._documents.clear()
        self._chat_history.clear()
