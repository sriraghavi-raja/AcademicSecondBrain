import os
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.schema import QueryBundle
from src.rag.ingestion.reader import load_documents_from_path
from src.rag.ingestion.ingestion import run_ingestion
from src.rag.ingestion.indexer import create_hierarchical_index
from src.rag.retrieval.retreiver import build_query_engine

def test_hybrid_retrieval():
    Settings.embed_model=OpenAIEmbedding(
        model="text-embedding-ada-002",
        api_base="http://127.0.0.1:1234/v1",
        api_key="lmstudio"
    )
    Settings.llm=OpenAI(
        model="gpt-3.5-turbo",
        api_base="http://127.0.0.1:1234/v1",
        api_key="lmstudio"
    )
    print("1. Loading Documents...")
    data_path = r"E:/College Projects/llamaIndex/AcademicSecondBrain/src/data"
    documents = load_documents_from_path(data_path)
    print(f"   Loaded {len(documents)} document objects.")

    print("\n2. Running Ingestion Pipeline...")
    all_nodes, leaf_nodes = run_ingestion(documents)
    print(f"   Generated {len(all_nodes)} total nodes in the hierarchy.")

    print("\n3. Building ChromaDB Index...")
    index = create_hierarchical_index(all_nodes, leaf_nodes, db_path="./chroma_db")

    print("\n4. Building Query Engine from retreiver.py...")
    # Import and initialize directly from retreiver.py!
    query_engine = build_query_engine(index)

    print("\n5. Testing Retrieval...")
    test_question = "What is the main topic of these documents?"
    bundle=QueryBundle(test_question)
    print(f"   Q: {test_question}")

    # Run retrieval
    retrieved_nodes = query_engine.retrieve(bundle)

    print(f"\n   Successfully retrieved & reranked down to {len(retrieved_nodes)} final nodes!")
    print("\n--- Retrieved Chunks ---")
    for i, node_with_score in enumerate(retrieved_nodes):
        node = node_with_score.node
        print(f"\nSource {i+1} | Length: {len(node.text)} chars | Score: {node_with_score.score:.3f}")
        preview = node.text[:250].replace("\n", " ")
        print(f"Preview: {preview}...")

if __name__ == "__main__":
    test_hybrid_retrieval()