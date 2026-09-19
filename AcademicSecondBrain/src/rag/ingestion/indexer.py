import os
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.vector_stores.chroma import ChromaVectorStore

PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "academic_collection")
DOCSTORE_FILE = "docstore.json"


def load_or_create_index(
        db_path: str = CHROMA_PATH,
        persist_dir: str = PERSIST_DIR
) -> VectorStoreIndex:
    """
    Loads the persisted index, or creates and persists an empty one on the first start.

    Nothing is ingested here: every document enters the index through the upload endpoint,
    stamped with the user who owns it.
    """
    chroma_collection = chromadb.PersistentClient(path=db_path).get_or_create_collection(CHROMA_COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    # 1. LOAD EXISTING: rehydrate the docstore (parent and child nodes) next to the Chroma vectors
    if os.path.exists(os.path.join(persist_dir, DOCSTORE_FILE)):
        print("--> Loading index and docstore from disk...")
        storage_context = StorageContext.from_defaults(
            persist_dir=persist_dir,
            vector_store=vector_store
        )
        return load_index_from_storage(storage_context)

    # Vectors without their docstore cannot be served: parents for auto-merging and BM25 are missing.
    if chroma_collection.count() > 0:
        raise RuntimeError(
            f"Chroma at '{db_path}' holds vectors but '{persist_dir}' has no {DOCSTORE_FILE}. "
            "Restore the storage folder or remove the Chroma folder to start from an empty index."
        )

    # 2. CREATE NEW: start empty and save it so the next start takes the load path
    print("--> No existing index found. Creating an empty index...")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(nodes=[], storage_context=storage_context)
    storage_context.persist(persist_dir=persist_dir)
    return index
