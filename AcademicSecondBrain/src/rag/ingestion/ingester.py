import threading
import os
from typing import List, Dict, Any, Union
from pathlib import Path
from llama_index.core import VectorStoreIndex

from src.rag.ingestion.metadata import OWNER_KEY, stamp_documents
from src.rag.ingestion.reader import load_documents_from_path
from src.rag.ingestion.ingestion import run_ingestion

ingest_lock = threading.Lock()


def ingest_new_documents(
        file_paths: List[Union[str, Path]],
        index: VectorStoreIndex,
        owner_id: str,
        persist_dir: str = None
) -> Dict[str, Any]:
    """
    Dynamically ingests new documents into the live VectorStoreIndex, owned by owner_id.
    Force-inserts everything without checking for duplicates.
    """
    if persist_dir is None:
        persist_dir = os.getenv("PERSIST_DIR", "./storage")

    with ingest_lock:
        # 1. Load Documents and mark them with their owner
        documents = load_documents_from_path(file_paths)
        stamp_documents(documents, owner_id)

        # 2. Run ingestion
        all_nodes, leaf_nodes = run_ingestion(documents)

        # 3. Native Runtime Insert: Inject vectors and docstore nodes live
        index.docstore.add_documents(all_nodes)
        index.insert_nodes(leaf_nodes)

        # 4. Save to disk so it survives a server restart
        index.storage_context.persist(persist_dir=persist_dir)

        return {
            "status": "success",
            "message": f"Successfully ingested file(s).",
            "added_total_nodes": len(all_nodes),
            "added_leaf_nodes": len(leaf_nodes)
        }


def delete_document(
        file_name: str,
        index: VectorStoreIndex,
        owner_id: str,
        persist_dir: str = None
) -> Dict[str, Any]:
    """
    Erases owner_id's document from both ChromaDB and the local docstore.

    Only nodes owned by owner_id whose file name or path equals file_name exactly are touched, so one
    user can never delete another user's document, and 'notes.pdf' never matches 'my_notes.pdf'.
    """
    if persist_dir is None:
        persist_dir = os.getenv("PERSIST_DIR", "./storage")

    with ingest_lock:
        clean_query = file_name.strip().lower()

        # 1. Scan docstore for the owner's parent and child nodes of this file
        nodes_to_delete = {}
        for node_id, node in list(index.docstore.docs.items()):
            if node.metadata.get(OWNER_KEY) != owner_id:
                continue
            meta_name = node.metadata.get("file_name", "").lower()
            meta_path = node.metadata.get("file_path", "").lower()
            if clean_query in (meta_name, meta_path):
                nodes_to_delete[node_id] = node

        if not nodes_to_delete:
            return {"status": "error", "message": f"Document '{file_name}' not found."}

        # 2. Purge vector embeddings first (only leaf nodes are embedded). If this fails nothing else has changed.
        leaf_ids = [node_id for node_id, node in nodes_to_delete.items() if not node.child_nodes]
        if leaf_ids:
            index.vector_store.delete_nodes(node_ids=leaf_ids)

        # 3. Remove the owner's nodes (parents + children) from the local docstore, node by node so that a
        #    source-document id shared with another user's upload is never swept up.
        for node_id in nodes_to_delete:
            index.docstore.delete_document(node_id, raise_error=False)

        # 4. Persist updated storage context to disk
        index.storage_context.persist(persist_dir=persist_dir)

        return {
            "status": "success",
            "message": f"Document '{file_name}' permanently deleted ({len(nodes_to_delete)} docstore nodes removed)."
        }
