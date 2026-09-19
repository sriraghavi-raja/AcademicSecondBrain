import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import Settings
from llama_index.embeddings.openai_like import OpenAILikeEmbedding

from src.rag.synthesis.engine import get_academic_llm
from src.rag.ingestion.indexer import PERSIST_DIR, load_or_create_index
from src.rag.retrieval.retreiver import RetrieverFactory, build_postprocessors
# from src.api import chat_router
from src.api import chat_router, sessions_router, documents_router, skills_router, github_router, study_router, career_router, profile_router, dashboard_router, auth_router, admin_router
from src.api.auth import get_current_user
from src.rag.registry import auth as auth_registry
from src.services.auth_service import AuthService
from src.rag.registry import skills
from src.rag.registry import study
from src.rag.registry import career
from src.services import DocumentService, RagService, SessionService

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_registry.init_db()
    app.state.auth_service = AuthService()
    skills.init_db()
    study.init_db()
    career.init_db()
    # 1. Fetch Groq API Key from environment
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing!")

    os.environ["OPENAI_API_KEY"] = groq_api_key

    # 2. Instantiate Groq LLM and assign globally
    groq_llm = get_academic_llm(api_key=groq_api_key)
    Settings.llm = groq_llm
    app.state.llm = groq_llm

    # 3. Configure Local Embedding Model dynamically via Env
    embed_api_base = os.getenv("EMBEDDING_API_BASE", "http://localhost:1234/v1")

    Settings.embed_model = OpenAILikeEmbedding(
    model_name="text-embedding-nomic-embed-text-v1.5@q8_0",
    api_base=embed_api_base,
    api_key="lm-studio",
)

    # Documents are ingested per user through the upload endpoint, never at startup
    print("1. Creating/Loading hierarchical index...")
    index = load_or_create_index()

    print("\n2. Building retriever factory and postprocessors...")
    retriever_factory = RetrieverFactory(index)
    postprocessors = build_postprocessors()

    # Store state globally for routers to access
    app.state.index = index
    app.state.retriever_factory = retriever_factory
    app.state.postprocessors = postprocessors
    app.state.rag_service = RagService(retriever_factory, groq_llm, postprocessors)
    app.state.document_service = DocumentService(
        index=index,
        retriever_factory=retriever_factory,
        upload_dir=os.getenv("UPLOAD_DIR", "uploads"),
        persist_dir=PERSIST_DIR,
    )
    app.state.session_service = SessionService()

    yield


app = FastAPI(
    title="RAG Backend API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Mount Routers
protected_dependencies = [Depends(get_current_user)]
app.include_router(chat_router, dependencies=protected_dependencies)
app.include_router(sessions_router, dependencies=protected_dependencies)
app.include_router(documents_router, dependencies=protected_dependencies)
app.include_router(skills_router, dependencies=protected_dependencies)
app.include_router(github_router, dependencies=protected_dependencies)
app.include_router(study_router, dependencies=protected_dependencies)
app.include_router(career_router, dependencies=protected_dependencies)
app.include_router(profile_router, dependencies=protected_dependencies)
app.include_router(dashboard_router, dependencies=protected_dependencies)
app.include_router(auth_router)
app.include_router(admin_router)

@app.get("/health", tags=["Health"])
def health_check(request: Request):
    return {
        "status": "healthy",
        "pipeline_ready": getattr(request.app.state, "retriever_factory", None) is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)