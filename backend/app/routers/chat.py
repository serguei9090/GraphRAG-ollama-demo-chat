from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.graphrag import (
    GraphRAGConfigurationError,
    GraphRAGService,
    StubGraphRAGChatEngine,
)
from ..services.ingestion import DataDirectoryIngestor

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    prompt: str


def get_engine(request: Request) -> GraphRAGService | StubGraphRAGChatEngine:
    return request.app.state.engine  # type: ignore[attr-defined]


def get_ingestor(request: Request) -> DataDirectoryIngestor:
    return request.app.state.ingestor  # type: ignore[attr-defined]


@router.post("/ingest")
def ingest_documents(
    ingestor: DataDirectoryIngestor = Depends(get_ingestor),
    engine: GraphRAGService | StubGraphRAGChatEngine = Depends(get_engine),
) -> dict:
    documents = ingestor.collect_documents()
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found for ingestion")

    if isinstance(engine, GraphRAGService):
        try:
            engine.reset()
            result = engine.ingest(documents)
        except GraphRAGConfigurationError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    else:
        engine.reset()
        result = engine.ingest(documents)
        result["using_stub"] = True
        result["graph_name"] = None
        result["ontology_path"] = None
        result["ontology_refreshed"] = False
        result["document_names"] = [doc.name for doc in documents]
    return result


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    ingestor: DataDirectoryIngestor = Depends(get_ingestor),
) -> dict:
    contents = await file.read()
    saved_path = ingestor.persist_upload(file.filename, contents)
    return {"filename": file.filename, "stored_at": str(saved_path)}


@router.get("/documents")
def list_documents(engine: GraphRAGService | StubGraphRAGChatEngine = Depends(get_engine)) -> dict:
    documents = engine.get_documents()
    payload = {
        "documents": [
            {
                "name": doc.name,
                "metadata": doc.metadata,
            }
            for doc in documents
        ]
    }
    if isinstance(engine, GraphRAGService):
        payload["using_stub"] = engine.using_stub
    else:
        payload["using_stub"] = True
    return payload


@router.post("/stream")
async def chat(
    request: ChatRequest, engine: GraphRAGService | StubGraphRAGChatEngine = Depends(get_engine)
) -> StreamingResponse:

    async def response_generator():
        try:
            async for chunk in engine.stream_chat(request.prompt):
                yield chunk
        except GraphRAGConfigurationError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return StreamingResponse(response_generator(), media_type="text/plain")
