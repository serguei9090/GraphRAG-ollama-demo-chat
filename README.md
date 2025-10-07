# GraphRAG Ollama Demo Chat

This repository provides a full-stack demonstration of building a lightweight GraphRAG-style chat interface on top of an Ollama-like backend. The project includes a FastAPI service for data ingestion and chat streaming, a Vite + React + Tailwind frontend, and an automated test suite for both layers.

## Repository Structure

```
backend/          # FastAPI application
  app/
    main.py       # FastAPI entrypoint
    routers/      # Chat router definitions
    services/     # Lightweight GraphRAG + ingestion helpers
frontend/         # Vite + React + Tailwind SPA
  src/            # React application source
  vite.config.ts  # Vite configuration with API proxy
  vitest.config.ts# Vitest test configuration
  package.json    # Frontend dependencies and scripts
data/
  pdf/            # Drop PDF documents for ingestion
  txt/            # Drop TXT documents for ingestion
  url/            # Add URL manifests (JSON array or line-separated)
tests/
  backend/        # Pytest suite for API and ingestion
  frontend/       # Vitest suite for React components
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) [Ollama](https://ollama.ai/) runtime if you plan to replace the stub GraphRAG implementation with a real model.

## Backend Setup

1. Create and activate a virtual environment.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install backend dependencies.

   ```bash
   pip install fastapi uvicorn[standard] pydantic PyPDF2 pytest
   ```

3. Run the FastAPI application.

   ```bash
   uvicorn backend.app.main:app --reload
   ```

### Data Directories

The backend automatically watches three folders under `data/`:

- `data/pdf/`: Place PDF documents here. PyPDF2 is used to extract text when available.
- `data/txt/`: Place plain text documents here.
- `data/url/`: Create `.txt` manifests containing either JSON arrays of URLs or one URL per line. These are loaded as virtual documents.

You can also upload `.pdf` and `.txt` files from the frontend, which will store them in the appropriate directory before ingestion.

### API Endpoints

- `GET /health`: Simple health check.
- `POST /chat/upload`: Upload a `.pdf` or `.txt` file. The backend stores the file and makes it available for ingestion.
- `POST /chat/ingest`: Read documents from the data directories and load them into the in-memory GraphRAG stub.
- `GET /chat/documents`: List the currently ingested documents.
- `POST /chat/stream`: Stream a chat response based on the ingested documents. The request body should be JSON with a `prompt` field.

## Frontend Setup

1. Install dependencies.

   ```bash
   cd frontend
   npm install
   ```

2. Run the development server.

   ```bash
   npm run dev
   ```

The Vite dev server proxies API requests from `/api/*` to the FastAPI backend running on `http://localhost:8000`.

## Running Tests

### Backend Tests

From the repository root (with the virtual environment activated):

```bash
pytest
```

### Frontend Tests

From the `frontend/` directory:

```bash
npm run test
```

## End-to-End Verification

1. Start the FastAPI server (`uvicorn backend.app.main:app --reload`).
2. Start the Vite dev server (`npm run dev` from `frontend/`).
3. Navigate to `http://localhost:5173`.
4. Upload one or more `.pdf` or `.txt` files or manually drop them in the `data/` folders.
5. Click **Ingest Documents** to load the content into the chat engine.
6. Interact with the chat panel to query the ingested knowledge base. Responses stream live from the backend.

## Extending the Demo

The current GraphRAG pipeline is an in-memory stub designed for educational and testing purposes. To integrate a real GraphRAG + Ollama workflow, replace the logic in `backend/app/services/graphrag.py` with calls to your preferred embedding store and Ollama model.

Contributions and improvements are welcome!
