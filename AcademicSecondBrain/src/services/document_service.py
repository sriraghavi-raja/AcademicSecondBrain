"""Document application services backed by the existing RAG implementation."""

import hashlib
import os
import re
import shutil
import uuid
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any, BinaryIO, Optional

from fastapi import HTTPException

from src.rag.ingestion.ingester import ingest_new_documents, remove_file_nodes
from src.rag.registry import documents as document_registry
from src.rag.registry.documents import DuplicateDocumentError

ALLOWED_EXTENSIONS = (".pdf", ".docx", ".pptx", ".txt", ".md")
DEFAULT_MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
STORED_FILE_NAME = "document"
COPY_CHUNK_BYTES = 1024 * 1024
SAFE_PATH_COMPONENT = re.compile(r"[A-Za-z0-9_-]+")


def _display_name(filename: Optional[str]) -> str:
    """The name to show for an upload: no folders (either separator style), no control characters."""
    name = PureWindowsPath(filename or "").name
    name = "".join(character for character in name if character.isprintable()).strip()
    if name in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="A filename is required.")
    return name[:255]


class DocumentService:
    def __init__(
        self,
        index: Any,
        retriever_factory: Any,
        upload_dir: str = "uploads",
        persist_dir: Optional[str] = None,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ):
        self.index = index
        self.retriever_factory = retriever_factory
        self.upload_dir = upload_dir
        self.persist_dir = persist_dir
        self.max_upload_bytes = max_upload_bytes

    def list_documents(self, owner_id: str) -> list[dict[str, Any]]:
        if not self.index:
            raise HTTPException(status_code=503, detail="Vector index is not initialized.")

        return [self._api_shape(record) for record in document_registry.list_documents(owner_id)]

    def get_document(self, owner_id: str, document_id: str) -> dict[str, Any]:
        record = document_registry.get_document(owner_id, document_id)
        if record is None or record["status"] != "ready":
            raise HTTPException(status_code=404, detail="Document not found.")
        return self._api_shape(record)

    def ingest_document(self, owner_id: str, file_bytes: BinaryIO, filename: Optional[str]) -> dict[str, Any]:
        if not self.index or not self.retriever_factory:
            raise HTTPException(status_code=503, detail="RAG system is not initialized.")

        display_name = _display_name(filename)
        extension = PurePath(display_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}.",
            )

        # The stored name is fixed, so nothing the client sends ever becomes part of a filesystem path.
        file_id = str(uuid.uuid4())
        directory = self._file_directory(owner_id, file_id)
        stored_path = directory / f"{STORED_FILE_NAME}{extension}"
        directory.mkdir(parents=True)
        succeeded = False
        try:
            sha256, size_bytes = self._save_upload(file_bytes, stored_path)
            try:
                document_registry.create_document(
                    file_id, owner_id, display_name, str(stored_path), sha256, size_bytes
                )
            except DuplicateDocumentError:
                existing = document_registry.find_by_hash(owner_id, sha256)
                name = existing["filename"] if existing else "another document"
                raise HTTPException(status_code=409, detail=f"You already uploaded this file as '{name}'.")

            try:
                result = ingest_new_documents(
                    [str(stored_path)], self.index, owner_id, file_id, display_name, persist_dir=self.persist_dir
                )
            except Exception:
                document_registry.delete_document(owner_id, file_id)
                raise

            document_registry.mark_ready(file_id, result["added_leaf_nodes"])
            succeeded = True
        finally:
            if not succeeded:
                shutil.rmtree(directory, ignore_errors=True)
        self.retriever_factory.invalidate(owner_id)

        return {
            "message": "Document ingested successfully",
            "document_id": file_id,
            "filename": display_name,
            "metadata": {
                "added_total_nodes": result.get("added_total_nodes", 0),
                "added_leaf_nodes": result.get("added_leaf_nodes", 0),
            },
        }

    def delete_document(self, owner_id: str, document_id: str) -> dict[str, str]:
        if not self.index or not self.retriever_factory:
            raise HTTPException(status_code=503, detail="RAG system is not initialized.")

        record = document_registry.get_document(owner_id, document_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Index first: if that fails the record stays and the delete can simply be retried.
        remove_file_nodes(self.index, owner_id, document_id, persist_dir=self.persist_dir)
        shutil.rmtree(self._file_directory(owner_id, document_id), ignore_errors=True)
        document_registry.delete_document(owner_id, document_id)
        self.retriever_factory.invalidate(owner_id)

        return {"message": f"Document {record['filename']} deleted"}

    def recover_interrupted_uploads(self) -> int:
        """
        Removes uploads that were still processing when the server stopped: their nodes, their files
        and their records. Call once at startup. Returns how many were cleaned up.
        """
        interrupted = document_registry.list_processing()
        for record in interrupted:
            owner_id, file_id = record["owner_id"], record["file_id"]
            remove_file_nodes(self.index, owner_id, file_id, persist_dir=self.persist_dir)
            shutil.rmtree(self._file_directory(owner_id, file_id), ignore_errors=True)
            document_registry.delete_document(owner_id, file_id)
            self.retriever_factory.invalidate(owner_id)
        return len(interrupted)

    def _file_directory(self, owner_id: str, file_id: str) -> Path:
        for component in (owner_id, file_id):
            if not SAFE_PATH_COMPONENT.fullmatch(component):
                raise ValueError("Unsafe identifier for a storage path")
        return Path(self.upload_dir) / owner_id / file_id

    def _save_upload(self, file_bytes: BinaryIO, path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size_bytes = 0
        with open(path, "wb") as buffer:
            while chunk := file_bytes.read(COPY_CHUNK_BYTES):
                size_bytes += len(chunk)
                if size_bytes > self.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File is larger than the {self.max_upload_bytes // (1024 * 1024) or 1} MB limit.",
                    )
                digest.update(chunk)
                buffer.write(chunk)
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        return digest.hexdigest(), size_bytes

    @staticmethod
    def _api_shape(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": record["file_id"],
            "filename": record["filename"],
            "chunk_count": record["chunk_count"],
            "ingested_at": record["created_at"],
        }
