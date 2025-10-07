from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.graphrag import GraphRAGChatEngine
from ..services.ingestion import DataDirectoryIngestor

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    prompt: str


def get_engine() -> GraphRAGChatEngine:
    return router.state.engine  # type: ignore[attr-defined]


def get_ingestor() -> DataDirectoryIngestor:
    return router.state.ingestor  # type: ignore[attr-defined]


@router.post("/ingest")
def ingest_documents(ingestor: DataDirectoryIngestor = Depends(get_ingestor), engine: GraphRAGChatEngine = Depends(get_engine)) -> dict:
    documents = ingestor.collect_documents()
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found for ingestion")
    return engine.ingest(documents)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    ingestor: DataDirectoryIngestor = Depends(get_ingestor),
) -> dict:
    contents = await file.read()
    saved_path = ingestor.persist_upload(file.filename, contents)
    return {"filename": file.filename, "stored_at": str(saved_path)}


@router.get("/documents")
def list_documents(engine: GraphRAGChatEngine = Depends(get_engine)) -> dict:
    return {"documents": [doc.name for doc in engine.get_documents()]}


@router.post("/stream")
async def chat(request: ChatRequest, engine: GraphRAGChatEngine = Depends(get_engine)) -> StreamingResponse:
    async def response_generator():
        async for chunk in engine.stream_chat(request.prompt):
            yield chunk

    return StreamingResponse(response_generator(), media_type="text/plain")
