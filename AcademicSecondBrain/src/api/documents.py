from typing import Annotated

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File

from src.api.auth import get_current_user

router = APIRouter(prefix="/api", tags=["Documents"])

@router.get("/docs")
def get_documents_endpoint(request: Request, current_user: Annotated[dict, Depends(get_current_user)]):
    """Retrieves a list of the caller's active documents in the RAG system."""
    try:
        return request.app.state.document_service.list_documents(current_user["user_id"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docs/upload")
def upload_document_endpoint(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    file: UploadFile = File(...)
):
    """
    Uploads and ingests a new document (PDF, DOCX, PPTX, TXT or MD) owned by the caller.

    A plain def on purpose: FastAPI runs it in a worker thread, so the slow embedding work
    does not freeze every other request, including streaming chats.
    """
    try:
        return request.app.state.document_service.ingest_document(current_user["user_id"], file.file, file.filename)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/docs/{document_id}")
def delete_document_endpoint(
    document_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Deletes one of the caller's documents from the vector store and docstore.
    """
    try:
        return request.app.state.document_service.delete_document(current_user["user_id"], document_id)

    except HTTPException:
        # Re-raise HTTP exceptions to maintain the correct status code (e.g., 404 vs 500)
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
