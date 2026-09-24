"""Restricts chat (and its tools, in agent mode) to documents the caller actually owns."""

from typing import FrozenSet, Iterable, Optional

from src.rag.registry import documents as document_registry


class DocumentAccessError(ValueError):
    """One of the given document ids does not exist, is not fully indexed, or belongs to someone else."""

    def __init__(self, document_id: str):
        super().__init__(f"Document not found: {document_id}")
        self.document_id = document_id


def validate_document_ids(user_id: str, document_ids: Optional[Iterable[str]]) -> Optional[FrozenSet[str]]:
    """
    Checks that every id is one of user_id's own, fully indexed documents.

    Returns None when document_ids is empty or None, meaning "no restriction" rather than "match
    nothing" — callers treat None as "search everything the user owns".
    """
    if not document_ids:
        return None
    validated = set()
    for document_id in document_ids:
        record = document_registry.get_document(user_id, document_id)
        if record is None or record["status"] != "ready":
            raise DocumentAccessError(document_id)
        validated.add(document_id)
    return frozenset(validated)
