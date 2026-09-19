"""Ownership metadata stamped on every ingested node.

LlamaIndex vector stores overwrite the metadata keys doc_id, document_id and ref_doc_id with the source
document's id, so ownership keys must never use those names.
"""

from typing import List

from llama_index.core import Document

OWNER_KEY = "owner_id"

# Bookkeeping that must not end up in embeddings or in the prompt shown to the LLM. file_path is included
# because it exposes server paths.
HIDDEN_METADATA_KEYS = [OWNER_KEY, "file_path"]


def stamp_documents(documents: List[Document], owner_id: str) -> None:
    """Marks every document with its owner. Child nodes inherit the metadata when the documents are parsed."""
    for document in documents:
        document.metadata[OWNER_KEY] = owner_id
        document.excluded_embed_metadata_keys = sorted({*document.excluded_embed_metadata_keys, *HIDDEN_METADATA_KEYS})
        document.excluded_llm_metadata_keys = sorted({*document.excluded_llm_metadata_keys, *HIDDEN_METADATA_KEYS})
