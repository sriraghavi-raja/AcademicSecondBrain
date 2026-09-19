import threading
import os
from typing import List, Dict, Any, Union
from pathlib import Path
from llama_index.core import VectorStoreIndex

from src.rag.ingestion.metadata import FILE_KEY, OWNER_KEY, stamp_documents
from src.rag.ingestion.reader import load_documents_from_path
from src.rag.ingestion.ingestion import run_ingestion

ingest_lock = threading.Lock()


def _purge_file_nodes(index: VectorStoreIndex, owner_id: str, file_id: str) -> int:
    """
    Removes every node of one upload from Chroma and the docstore. Caller must hold ingest_lock.

    Nodes are found by owner and file id and removed one by one, so nothing that belongs to another
    upload or another user can be swept up.
    """
    nodes = {
        node_id: node
        for node_id, node in list(index.docstore.docs.items())
        if node.metadata.get(OWNER_KEY) == owner_id and node.metadata.get(FILE_KEY) == file_id
    }

    # Purge vector embeddings first (only leaf nodes are embedded). If this fails nothing else has changed.
    leaf_ids = [node_id for node_id, node in nodes.items() if not node.child_nodes]
    if leaf_ids:
        index.vector_store.delete_nodes(node_ids=leaf_ids)

    for node_id in nodes:
        index.docstore.delete_document(node_id, raise_error=False)
    return len(nodes)


def ingest_new_documents(
        file_paths: List[Union[str, Path]],
        index: VectorStoreIndex,
        owner_id: str,
        file_id: str,
        display_name: str,
        persist_dir: str = None
) -> Dict[str, Any]:
    """
    Dynamically ingests one upload into the live VectorStoreIndex, owned by owner_id.

    If anything fails while the nodes are being added, every node of this upload is removed again so the
    docstore and the vector store never disagree.
    """
    if persist_dir is None:
        persist_dir = os.getenv("PERSIST_DIR", "./storage")

    with ingest_lock:
        # 1. Load Documents and mark them with their owner and upload id
        documents = load_documents_from_path(file_paths)
        stamp_documents(documents, owner_id, file_id, display_name)

        # 2. Run ingestion
        all_nodes, leaf_nodes = run_ingestion(documents)

        try:
            # 3. Native Runtime Insert: Inject vectors and docstore nodes live
            index.docstore.add_documents(all_nodes)
            index.insert_nodes(leaf_nodes)

            # 4. Save to disk so it survives a server restart
            index.storage_context.persist(persist_dir=persist_dir)
        except Exception:
            _purge_file_nodes(index, owner_id, file_id)
            try:
                index.storage_context.persist(persist_dir=persist_dir)
            except Exception:
                pass  # best effort: the next successful write persists the cleaned state
            raise

        return {
            "status": "success",
            "message": f"Successfully ingested file(s).",
            "added_total_nodes": len(all_nodes),
            "added_leaf_nodes": len(leaf_nodes)
        }


def remove_file_nodes(
        index: VectorStoreIndex,
        owner_id: str,
        file_id: str,
        persist_dir: str = None
) -> int:
    """Erases one of owner_id's uploads from ChromaDB and the local docstore. Returns the nodes removed."""
    if persist_dir is None:
        persist_dir = os.getenv("PERSIST_DIR", "./storage")

    with ingest_lock:
        removed = _purge_file_nodes(index, owner_id, file_id)
        index.storage_context.persist(persist_dir=persist_dir)
        return removed
