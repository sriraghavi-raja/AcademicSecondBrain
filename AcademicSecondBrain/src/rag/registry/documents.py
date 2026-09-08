from typing import List, Dict, Any
from llama_index.core import VectorStoreIndex


def list_documents(index: VectorStoreIndex) -> List[Dict[str, Any]]:
    """Returns a list of all active documents by safely bypassing VectorStore constraints and querying the docstore directly."""
    docs_map = {}

    # Iterate over all raw nodes in our local document store
    for node in index.docstore.docs.values():
        ref_doc_id = node.ref_doc_id

        if not ref_doc_id:
            continue

        metadata = node.metadata
        file_path = metadata.get("file_path", "unknown_path")
        file_name = metadata.get("file_name", ref_doc_id)

        if file_path not in docs_map:
            docs_map[file_path] = {
                "file_name": file_name,
                "file_path": file_path,
                "part_ids": set()  # Use a set temporarily to avoid duplicates
            }

        docs_map[file_path]["part_ids"].add(ref_doc_id)

    # Convert sets back to lists for clean JSON serialization
    for doc in docs_map.values():
        doc["part_ids"] = list(doc["part_ids"])

    return list(docs_map.values())