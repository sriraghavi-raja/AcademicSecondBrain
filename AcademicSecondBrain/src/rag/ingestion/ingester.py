import threading
import os
from typing import List, Dict, Any, Union
from pathlib import Path
from llama_index.core import VectorStoreIndex
from llama_index.retrievers.bm25 import BM25Retriever

from src.rag.ingestion.reader import load_documents_from_path
from src.rag.ingestion.ingestion import run_ingestion

ingest_lock = threading.Lock()


def ingest_new_documents(
        file_paths: List[Union[str, Path]],
        index: VectorStoreIndex,
        persist_dir: str = None
) -> Dict[str, Any]:
    """
    Dynamically ingests new documents into the live VectorStoreIndex.
    Force-inserts everything without checking for duplicates.
    """
    if persist_dir is None:
        persist_dir = os.getenv("PERSIST_DIR", "./storage")

    with ingest_lock:
        # 1. Load Documents
        documents = load_documents_from_path(file_paths)

        # 2. Run ingestion
        all_nodes, leaf_nodes = run_ingestion(documents)

        # 3. Native Runtime Insert: Inject vectors and docstore nodes live
        index.docstore.add_documents(all_nodes)
        index.insert_nodes(leaf_nodes)

        # 4. Save to disk so it survives a server restart
        index.storage_context.persist(persist_dir=persist_dir)

        # 5. Rebuild BM25 Retriever with the newly expanded docstore
        bm25_retriever = BM25Retriever.from_defaults(
            docstore=index.docstore,
            similarity_top_k=12
        )

        return {
            "status": "success",
            "message": f"Successfully ingested file(s).",
            "added_total_nodes": len(all_nodes),
            "added_leaf_nodes": len(leaf_nodes),
            "bm25_retriever": bm25_retriever
        }


def delete_document(
        file_name: str,
        index: VectorStoreIndex,
        retriever_wrapper: Any,
        persist_dir: str = None
) -> Dict[str, Any]:
    """
    Completely erases a document from both ChromaDB and the local docstore
    by scrubbing all associated parent and child node IDs directly.
    """
    if persist_dir is None:
        persist_dir = os.getenv("PERSIST_DIR", "./storage")

    with ingest_lock:
        clean_query = file_name.strip().lower()

        nodes_to_delete = []
        ref_doc_ids_to_delete = set()

        # 1. Scan docstore to collect all matching node IDs and parent ref_doc_ids
        for node_id, node in list(index.docstore.docs.items()):
            meta_name = node.metadata.get("file_name", "").lower()
            meta_path = node.metadata.get("file_path", "").lower()

            if clean_query == meta_name or clean_query == meta_path or clean_query in meta_name:
                nodes_to_delete.append(node_id)
                if node.ref_doc_id:
                    ref_doc_ids_to_delete.add(node.ref_doc_id)

        if not nodes_to_delete and not ref_doc_ids_to_delete:
            return {"status": "error", "message": f"Document '{file_name}' not found."}

        # 2. Purge vector embeddings from ChromaDB
        for ref_id in ref_doc_ids_to_delete:
            try:
                index.delete_ref_doc(ref_id, delete_from_docstore=False)
            except Exception:
                pass

        # 3. Explicitly remove all nodes (parents + children) from the local docstore
        for node_id in nodes_to_delete:
            index.docstore.delete_document(node_id, raise_error=False)

        for ref_id in ref_doc_ids_to_delete:
            index.docstore.delete_document(ref_id, raise_error=False)

        # 4. Persist updated storage context to disk
        index.storage_context.persist(persist_dir=persist_dir)

        # 5. Rebuild BM25 retriever from the pruned docstore and hot-swap
        new_bm25_retriever = BM25Retriever.from_defaults(
            docstore=index.docstore,
            similarity_top_k=12
        )
        retriever_wrapper.update_bm25(new_bm25_retriever)

        return {
            "status": "success",
            "message": f"Document '{file_name}' permanently deleted ({len(nodes_to_delete)} docstore nodes removed)."
        }