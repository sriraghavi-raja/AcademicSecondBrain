import os
import asyncio
from llama_index.core import Settings
from llama_index.embeddings.openai_like import OpenAILikeEmbedding

from src.rag.synthesis.engine import get_academic_llm
from src.rag.ingestion.reader import load_documents_from_path
from src.rag.ingestion.ingestion import run_ingestion
from src.rag.ingestion.indexer import create_hierarchical_index
from src.rag.retrieval.retreiver import build_retriever_stack
from src.rag.ingestion.ingester import ingest_new_documents, delete_document

# New imports for testing registry and stateless chat
from src.rag.registry.documents import list_documents
from src.rag.registry.sessions import list_sessions, get_session_history
from src.rag.synthesis.chat import handle_stateless_chat


async def main():
    # 1. Fetch Groq API Key from environment
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing!")

    os.environ["OPENAI_API_KEY"] = groq_api_key

    # 2. Instantiate Groq LLM and assign globally
    groq_llm = get_academic_llm(api_key=groq_api_key)
    Settings.llm = groq_llm

    # 3. Configure Local Embedding Model dynamically via Env
    data_path = os.path.join("src", "data")
    embed_api_base = os.getenv("EMBEDDING_API_BASE", "http://localhost:1234/v1")

    Settings.embed_model = OpenAILikeEmbedding(
        model_name="text-embedding-ada-002",
        api_base=embed_api_base,
        api_key="lm-studio",
    )

    # Ingestion & Indexing
    print("1. Loading documents & running ingestion pipeline...")
    documents = load_documents_from_path(data_path)
    all_nodes, leaf_nodes = run_ingestion(documents)

    print("\n2. Creating/Loading hierarchical index...")
    index = create_hierarchical_index(all_nodes, leaf_nodes)

    print("\n3. Building retriever and postprocessors...")
    retriever, postprocessors = build_retriever_stack(index)

    # Note: We are no longer building the ChatEngine here!
    # We will use the stateless handler per request to test the SQLite sessions.

    print("\n" + "=" * 65)
    print("          ACADEMIC SECOND BRAIN - TESTING SANDBOX          ")
    print("=" * 65)
    print(" Commands:")
    print("  /upload <path>    - Ingest a new document")
    print("  /docs             - List all active documents")
    print("  /delete <name>    - Delete a document by file_name")
    print("  /sessions         - List all chat sessions in SQLite")
    print("  /history          - View history of the current session")
    print("  /new              - Start a completely new chat session")
    print("  exit / quit       - End the program")
    print("=" * 65 + "\n")

    # Track the active session to simulate a connected frontend user
    active_session_id = None

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("\nEnding chat session. Goodbye!")
                break

            # --- DOCUMENT MANAGEMENT COMMANDS ---
            if user_input.lower().startswith("/upload "):
                filepath = user_input.split(" ", 1)[1].strip()
                if not os.path.exists(filepath):
                    print(f"\n[Error] File '{filepath}' not found.")
                    continue
                print(f"\n[System] Initiating dynamic upload for {filepath}...")
                result = ingest_new_documents([filepath], index)
                print(f"Status: {result['status']} | Msg: {result['message']}")
                if result.get("bm25_retriever"):
                    retriever.update_bm25(result["bm25_retriever"])
                    print("[System] Active BM25 Retriever stack updated successfully.")
                continue

            if user_input.lower() == "/docs":
                docs = list_documents(index)
                print("\n--- Active Documents ---")
                for d in docs:
                    print(f"- {d['file_name']} (Path: {d['file_path']} | Parts: {len(d['part_ids'])})")
                print("------------------------")
                continue

            if user_input.lower().startswith("/delete "):
                filename = user_input.split(" ", 1)[1].strip()
                print(f"\n[System] Attempting to delete '{filename}'...")
                result = delete_document(filename, index, retriever)
                print(f"Status: {result['status']} | Msg: {result['message']}")
                continue

            # --- SESSION MANAGEMENT COMMANDS ---
            if user_input.lower() == "/sessions":
                sessions = list_sessions()
                print("\n--- SQLite Sessions ---")
                for s in sessions:
                    marker = " (ACTIVE)" if s['session_id'] == active_session_id else ""
                    print(f"- ID: {s['session_id']} | Created: {s['created_at']}{marker}")
                print("-----------------------")
                continue

            if user_input.lower() == "/history":
                if not active_session_id:
                    print("\n[System] No active session history yet. Say hello first!")
                    continue
                history = get_session_history(active_session_id)
                print(f"\n--- History for {active_session_id[:8]}... ---")
                for msg in history:
                    print(f"[{msg['role'].upper()}]: {msg['content'][:100]}...")
                print("-----------------------------------")
                continue

            if user_input.lower() == "/new":
                active_session_id = None
                print("\n[System] Active session cleared. Next message will start a new session.")
                continue

            # --- STATELESS CHAT EXECUTION ---
            # This mimics exactly what the FastAPI route will do
            result = await handle_stateless_chat(
                message=user_input,
                retriever=retriever,
                llm=groq_llm,
                session_id=active_session_id,
                node_postprocessors=postprocessors
            )

            # Update active session based on what the stateless handler returns
            active_session_id = result["session_id"]

            print("\n" + "=" * 60)
            print("                      SYNTHESIZED ANSWER                     ")
            print("=" * 60)
            print(result["answer"])

            if result.get("sources"):
                print("\n" + "-" * 60)
                print("                       RETRIEVED SOURCES                     ")
                print("-" * 60)
                for idx, src in enumerate(result["sources"], 1):
                    page_val = src.get("page") or src.get("page_number", "N/A")
                    print(f"[{idx}] File: {src['file_name']} (Page: {page_val}) | Score: {src['score']}")
                    print(f"    Snippet: {src['snippet']}\n")

        except KeyboardInterrupt:
            print("\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n[Error] {e}")


if __name__ == "__main__":
    asyncio.run(main())