import os
from typing import List, Optional
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.schema import BaseNode
from llama_index.vector_stores.chroma import ChromaVectorStore

PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "academic_collection")


def create_hierarchical_index(
        all_nodes: Optional[List[BaseNode]] = None,
        leaf_nodes: Optional[List[BaseNode]] = None,
        db_path: str = CHROMA_PATH,
        persist_dir: str = PERSIST_DIR
) -> VectorStoreIndex:
    db = chromadb.PersistentClient(path=db_path)
    chroma_collection = db.get_or_create_collection(CHROMA_COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # 1. LOAD EXISTING: If Chroma has data AND storage dir exists
    if chroma_collection.count() > 0 and os.path.exists(persist_dir):
        print("--> Loading perfectly synced index and docstore from disk...")

        # Load storage context with both ChromaVectorStore and persisted docstore files
        storage_context = StorageContext.from_defaults(
            persist_dir=persist_dir,
            vector_store=vector_store
        )

        # Rehydrate full index including the docstore (parent and child nodes)
        index = load_index_from_storage(storage_context)
        return index

    # 2. CREATE NEW: If missing or empty
    else:
        print("--> No existing index found. Generating embeddings and building index...")
        if not all_nodes or not leaf_nodes:
            raise ValueError("Nodes required to create index.")

        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Save all parent and child nodes to the docstore for AutoMerging & BM25
        storage_context.docstore.add_documents(all_nodes)

        # Create the index (Embeds the leaf nodes into Chroma)
        index = VectorStoreIndex(nodes=leaf_nodes, storage_context=storage_context)

        # Save docstore and index metadata to disk
        storage_context.persist(persist_dir=persist_dir)
        print("--> Saved new embeddings and docstore to disk!")

        return index