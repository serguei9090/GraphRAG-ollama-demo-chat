"""Helper script to pre-build the GraphRAG ontology from local documents."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    from graphrag_sdk import Ontology
    from graphrag_sdk.models.litellm import LiteModel
    from graphrag_sdk.source import Source_FromRawText
except Exception as exc:  # pragma: no cover - external dependency
    print(f"GraphRAG SDK dependencies missing: {exc}", file=sys.stderr)
    sys.exit(1)

from backend.app.services.graphrag import GraphRAGConfig
from backend.app.services.ingestion import DataDirectoryIngestor


def main() -> int:
    base_path = Path(__file__).resolve().parents[1]

    load_dotenv(base_path / ".env", override=True)
    load_dotenv(override=True)

    config = GraphRAGConfig.from_env(base_path)

    ingestor = DataDirectoryIngestor(base_path)
    documents = ingestor.collect_documents()
    if not documents:
        print("No documents found in data/pdf, data/txt, or data/url", file=sys.stderr)
        return 1

    try:
        extract_model = LiteModel(model_name=config.extraction_model)
    except Exception as exc:  # pragma: no cover - model configuration
        print(f"Failed to initialise LiteLLM model '{config.extraction_model}': {exc}", file=sys.stderr)
        return 1

    sources = [Source_FromRawText(doc.content, instruction=f"Source: {doc.name}") for doc in documents]

    print(f"Building ontology from {len(sources)} sources using {config.extraction_model}...")
    ontology = Ontology.from_sources(sources=sources, model=extract_model, hide_progress=True)

    config.ontology_path.parent.mkdir(parents=True, exist_ok=True)
    config.ontology_path.write_text(json.dumps(ontology.to_json(), indent=2), encoding="utf-8")

    print(f"Ontology written to {config.ontology_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
