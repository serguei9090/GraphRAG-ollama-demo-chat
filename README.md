# GraphRAG Ollama Demo Chat

This project delivers a full-stack Retrieval-Augmented Generation (RAG) experience that combines the
[FalkorDB GraphRAG-SDK](https://github.com/FalkorDB/GraphRAG-SDK) with a local
[Ollama](https://ollama.ai/) deployment running the `llama3.1:8b` model. The backend exposes FastAPI
endpoints for ingesting PDFs, text files, and remote URLs into a knowledge graph and then streams
chat responses sourced from that graph. A Vite + React + Tailwind frontend consumes the API and
presents upload, status, and chat views. For development and CI the service can transparently fall
back to an in-memory stub engine, allowing the repository to be exercised without external services.

## Repository Structure

```
backend/          # FastAPI application
  app/
    main.py       # FastAPI entrypoint and application factory
    routers/      # API routers (chat + ingestion)
    services/     # GraphRAG integration and data ingestion utilities
frontend/         # Vite + React + Tailwind single-page application
  src/            # React components and API client
  vite.config.ts  # Development proxy configuration
  vitest.config.ts# Vitest test runner configuration
  package.json    # Frontend scripts and dependencies
data/
  pdf/            # Local PDFs ingested into the knowledge graph
  txt/            # Local plain-text files ingested into the graph
  url/            # `.txt` manifests pointing at remote URLs to fetch and ingest
tests/
  backend/        # Pytest suite exercising ingestion and streaming endpoints
  frontend/       # Vitest suite covering the React experience
```

## Prerequisites

To run the production GraphRAG pipeline you will need:

- Python 3.10+
- Node.js 18+
- Docker (to host FalkorDB)
- An [Ollama](https://ollama.ai/) runtime with the `llama3.1:8b` model pulled locally
- Credentials for your LiteLLM provider (for example `OPENAI_API_KEY`) used during ontology and
  Cypher generation

> **Tip:** When any of these dependencies are missing the backend logs a warning and falls back to
> the lightweight in-memory stub so the rest of the stack keeps functioning.

## Backend Setup

1. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. Copy the example environment file and update values as needed:

   ```bash
   cp .env.example .env
   ```

   | Variable | Description |
   | --- | --- |
   | `FALKORDB_HOST`, `FALKORDB_PORT` | Connection details for FalkorDB (defaults target the Docker setup below). |
   | `FALKORDB_USERNAME`, `FALKORDB_PASSWORD` | Optional FalkorDB credentials. |
   | `GRAPHRAG_KG_NAME` | Logical name for the knowledge graph. |
   | `GRAPHRAG_EXTRACTION_MODEL`, `GRAPHRAG_CYPHER_MODEL` | LiteLLM model identifiers (e.g. `openai/gpt-4.1`). |
   | `OLLAMA_MODEL`, `OLLAMA_BASE_URL` | Ollama QA model and endpoint (`llama3.1:8b` at `http://localhost:11434`). |
   | `GRAPHRAG_AUTO_REFRESH_ONTOLOGY` | When `true` (default) the ontology is regenerated on each ingest. |
   | `GRAPHRAG_RESET_BEFORE_INGEST` | Force a FalkorDB reset before every ingest operation. |
   | `GRAPHRAG_USE_STUB` | Set to `true` to explicitly opt into the in-memory stub. |

3. Start FalkorDB using Docker:

   ```bash
   docker run -p 6379:6379 -p 3000:3000 -it --rm -v $(pwd)/data:/data falkordb/falkordb:latest
   ```

4. Ensure the Ollama model is available locally:

   ```bash
   ollama pull llama3.1:8b
   # optional: run once to warm the model
   ollama run llama3.1:8b "ready"
   ```

5. Launch the FastAPI server (the example command enables the default live reload):

   ```bash
   uvicorn backend.app.main:app --reload
   ```

   On startup the service attempts to connect to FalkorDB, configure the GraphRAG SDK, and report
   whether it is using the real backend or the stub fallback.

### Data Directories and Ingestion

The application monitors three folders under `data/` and exposes upload endpoints for the same
formats:

- `data/pdf/` — Local PDFs (text is extracted with [`pypdf`](https://pypi.org/project/pypdf/)).
- `data/txt/` — UTF-8 encoded text files.
- `data/url/` — `.txt` manifests containing either JSON arrays or newline-delimited URLs. Content is
  fetched via `httpx` at ingest time and stored alongside metadata.

Each document is normalised into a GraphRAG source with SHA-1 hashes and source path metadata so you
can track provenance from the frontend.

## Frontend Setup

1. Install dependencies and start the development server:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. The Vite dev server proxies `/api/*` requests to `http://localhost:8000` by default. To target a
   different backend supply `VITE_API_BASE_URL` when running or building the frontend.

The UI surfaces the current backend mode (stub vs. GraphRAG), ingestion summaries, and document
metadata while providing a streaming chat pane powered by the `/chat/stream` endpoint.

## API Overview

- `GET /health` — Service liveness probe.
- `POST /chat/upload` — Upload a `.pdf` or `.txt` document (stored in `data/`).
- `POST /chat/ingest` — Collects local/remote documents, optionally resets FalkorDB, rebuilds the
  ontology, and returns an ingestion summary (`documents_ingested`, `graph_name`, `ontology_path`,
  `using_stub`, and per-document names).
- `GET /chat/documents` — Lists currently loaded documents including metadata (`path`, `sha1`) and
  reports the backend mode (`using_stub`).
- `POST /chat/stream` — Streams a response for the supplied `prompt`. When running against GraphRAG
  the service relays tokens from `ChatSession.send_message_stream`; in stub mode it emits a
  deterministic highlight summary.

## Running Tests

Backend tests rely on the stub to avoid external services. Ensure `GRAPHRAG_USE_STUB=true` in the
environment (Pytest automatically sets this in the provided fixtures):

```bash
pytest
```

Frontend tests run with Vitest and jsdom:

```bash
cd frontend
npm run test -- run
```

## End-to-End Verification Checklist

1. Start FalkorDB and verify port 6379 is reachable.
2. Pull `llama3.1:8b` with Ollama and ensure the daemon is running on `http://localhost:11434`.
3. Export your LiteLLM provider credentials (e.g. `export OPENAI_API_KEY=...`).
4. Populate `data/pdf`, `data/txt`, or `data/url` with sample documents.
5. Run the FastAPI backend and confirm the logs indicate `using_stub=False`.
6. Start the React frontend (`npm run dev`) and open `http://localhost:5173`.
7. Click **Ingest Documents** to build the FalkorDB graph and ontology.
8. Ask a question in the chat panel and observe streamed answers sourced from your documents.

If you see `using_stub=true` in the UI, double-check the FalkorDB container, LiteLLM credentials, and
Ollama endpoint. The fallback keeps the workflow usable even while dependencies are offline.

## Troubleshooting

- **`LiteLLM provider configuration error`** — Ensure the relevant API key (for example
  `OPENAI_API_KEY`, `GROQ_API_KEY`, etc.) is exported before starting the backend.
- **`Failed to connect to FalkorDB`** — Verify the Docker container is running and reachable at the
  host/port defined in `.env`.
- **Ollama streaming errors** — Confirm the daemon is listening on `OLLAMA_BASE_URL` and the
  specified model (`OLLAMA_MODEL`) is installed.
- **CI / offline environments** — Set `GRAPHRAG_USE_STUB=true` to continue using the in-memory
  fallback without external dependencies.

Happy hacking!
