from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from src.rag.registry.documents import list_documents
from src.rag.ingestion.ingester import ingest_new_documents, delete_document

router = APIRouter(prefix="/api", tags=["Documents"])

@router.get("/docs")
def get_documents_endpoint(request: Request):
    """Retrieves a list of all active documents in the RAG system."""
    try:
        return request.app.state.document_service.list_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docs/upload")
async def upload_document_endpoint(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Uploads and ingests a new document (PDF, DOCX, PPTX, etc.).
    """
    try:
        return request.app.state.document_service.ingest_document(file.file, file.filename)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.delete("/docs/{document_id}")
def delete_document_endpoint(document_id: str, request: Request):
    """
    Deletes a specific document from the vector store and docstore.
    """
    try:
        return request.app.state.document_service.delete_document(document_id)

    except HTTPException:
        # Re-raise HTTP exceptions to maintain the correct status code (e.g., 404 vs 500)
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))