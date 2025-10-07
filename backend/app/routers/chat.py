from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.graphrag import GraphRAGChatEngine
from ..services.ingestion import DataDirectoryIngestor

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    prompt: str


def get_engine(request: Request) -> GraphRAGChatEngine:
    return request.app.state.engine  # type: ignore[attr-defined]


def get_ingestor(request: Request) -> DataDirectoryIngestor:
    return request.app.state.ingestor  # type: ignore[attr-defined]


@router.post("/ingest")
def ingest_documents(ingestor: DataDirectoryIngestor = Depends(get_ingestor), engine: GraphRAGChatEngine = Depends(get_engine)) -> dict:
    documents = ingestor.collect_documents()
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found for ingestion")
    engine.reset()
    result = engine.ingest(documents)
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
def list_documents(engine: GraphRAGChatEngine = Depends(get_engine)) -> dict:
    return {"documents": [doc.name for doc in engine.get_documents()]}


@router.post("/stream")
async def chat(request: ChatRequest, engine: GraphRAGChatEngine = Depends(get_engine)) -> StreamingResponse:
    async def response_generator():
        async for chunk in engine.stream_chat(request.prompt):
            yield chunk

    return StreamingResponse(response_generator(), media_type="text/plain")
