"""Document application services backed by the existing RAG implementation."""

import os
import shutil
from typing import Any, BinaryIO

from fastapi import HTTPException

from src.rag.ingestion.ingester import delete_document, ingest_new_documents
from src.rag.registry.documents import list_documents


class DocumentService:
    def __init__(self, index: Any, retriever: Any, upload_dir: str = "uploads"):
        self.index = index
        self.retriever = retriever
        self.upload_dir = upload_dir

    def list_documents(self) -> list[dict[str, Any]]:
        if not self.index:
            raise HTTPException(status_code=503, detail="Vector index is not initialized.")

        raw_documents = list_documents(self.index)
        return [
            {
                "document_id": document.get("file_name", "unknown"),
                "filename": document.get("file_name", "unknown"),
                "file_path": document.get("file_path", "unknown"),
                "chunk_count": len(document.get("part_ids", [])),
                "ingested_at": "unknown",
            }
            for document in raw_documents
        ]

    def get_document(self, document_id: str) -> dict[str, Any]:
        for document in self.list_documents():
            if document["document_id"] == document_id:
                return document
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    def ingest_document(self, file_bytes: BinaryIO, filename: str) -> dict[str, Any]:
        if not self.index or not self.retriever:
            raise HTTPException(status_code=503, detail="RAG system is not initialized.")

        os.makedirs(self.upload_dir, exist_ok=True)
        file_path = os.path.join(self.upload_dir, filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file_bytes, buffer)

        result = ingest_new_documents([file_path], self.index)
        if result.get("bm25_retriever"):
            self.retriever.update_bm25(result["bm25_retriever"])

        return {
            "message": "Document ingested successfully",
            "document_id": filename,
            "metadata": {
                "added_total_nodes": result.get("added_total_nodes", 0),
                "added_leaf_nodes": result.get("added_leaf_nodes", 0),
                "file_path": file_path,
            },
        }

    def delete_document(self, document_id: str) -> dict[str, str]:
        if not self.index or not self.retriever:
            raise HTTPException(status_code=503, detail="RAG system is not initialized.")

        result = delete_document(
            file_name=document_id,
            index=self.index,
            retriever_wrapper=self.retriever,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))

        return {"message": f"Document {document_id} deleted"}