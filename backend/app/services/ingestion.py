"""Utilities for ingesting content from the data directories."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from .graphrag import Document

LOGGER = logging.getLogger(__name__)


class DataDirectoryIngestor:
    """Ingest documents from the repo's data directories."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.pdf_dir = base_path / "data" / "pdf"
        self.txt_dir = base_path / "data" / "txt"
        self.url_dir = base_path / "data" / "url"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.txt_dir.mkdir(parents=True, exist_ok=True)
        self.url_dir.mkdir(parents=True, exist_ok=True)

    def persist_upload(self, filename: str, data: bytes) -> Path:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            target_dir = self.pdf_dir
        else:
            target_dir = self.txt_dir
        target_path = target_dir / filename
        target_path.write_bytes(data)
        LOGGER.info("Stored upload at %s", target_path)
        return target_path

    def _read_pdf(self, path: Path) -> str:
        try:
            import PyPDF2  # type: ignore
        except Exception:  # pragma: no cover - optional dependency
            LOGGER.warning("PyPDF2 not available, returning placeholder text for %s", path)
            return f"PDF document at {path.name}"

        content = []
        with path.open("rb") as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:  # pragma: no cover - defensive
                    page_text = ""
                content.append(page_text)
        return "\n".join(content).strip()

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _read_url_manifest(self, path: Path) -> List[str]:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(item) for item in data]
        except json.JSONDecodeError:
            pass
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def collect_documents(self) -> List[Document]:
        documents: List[Document] = []

        if self.pdf_dir.exists():
            for pdf in sorted(self.pdf_dir.glob("*.pdf")):
                documents.append(Document(name=pdf.name, content=self._read_pdf(pdf), metadata={"source": "pdf"}))

        if self.txt_dir.exists():
            for txt in sorted(self.txt_dir.glob("*.txt")):
                documents.append(Document(name=txt.name, content=self._read_text(txt), metadata={"source": "txt"}))

        if self.url_dir.exists():
            for manifest in sorted(self.url_dir.glob("*.txt")):
                urls = self._read_url_manifest(manifest)
                documents.append(
                    Document(
                        name=manifest.name,
                        content="\n".join(urls),
                        metadata={"source": "url", "count": str(len(urls))},
                    )
                )

        return documents
