"""Utility classes that emulate a GraphRAG + Ollama pipeline.

These classes provide a lightweight shim that mimics the interface of a
GraphRAG backed conversational agent so that the FastAPI application can run
without the heavy dependencies.  The implementation keeps the ingested
content in memory and synthesises deterministic responses for tests.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, Iterable, List, Tuple


@dataclass
class Document:
    """Simple representation of an ingested document."""

    name: str
    content: str
    metadata: Dict[str, str] = field(default_factory=dict)


class GraphRAGChatEngine:
    """Tiny in-memory chat engine that mimics GraphRAG behaviour."""

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
            await asyncio.sleep(0)  # allow the event loop to switch context
            yield chunk + " "

    def reset(self) -> None:
        self._documents.clear()
        self._chat_history.clear()

    # Internal helpers -------------------------------------------------
    def _build_highlights(self, prompt: str) -> List[Tuple[Document, int]]:
        """Return documents ranked by lexical overlap with the prompt."""

        tokens = {token.lower() for token in prompt.split() if token}
        if not tokens or not self._documents:
            return []

        ranked: List[Tuple[Document, int]] = []
        for document in self._documents.values():
            score = sum(1 for token in tokens if token in document.content.lower())
            if score:
                ranked.append((document, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:3]

    def _render_answer(self, prompt: str, highlights: List[Tuple[Document, int]]) -> str:
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
