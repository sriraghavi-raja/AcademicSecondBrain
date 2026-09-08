import os
from os import environ
from typing import Dict, Any, List, Optional
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer, ResponseMode
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.llms.openai_like import OpenAILike
from dotenv import load_dotenv
from src.rag.synthesis.prompts import get_academic_prompt
load_dotenv()

def get_academic_llm(
        model_name: str = "openai/gpt-oss-20b",
        api_key: Optional[str] = None
) -> OpenAILike:
    """Configures the LLM using LMStudio OpenAI-compatible endpoint."""
    return OpenAILike(
        model=model_name,
        api_base="https://api.groq.com/openai/v1",
        api_key=api_key,
        temperature=0.2,
        is_chat_model=True
    )


def build_academic_query_engine(
        retriever: BaseRetriever,
        node_postprocessors: Optional[List[BaseNodePostprocessor]] = None,
        llm: Optional[OpenAILike] = None
) -> RetrieverQueryEngine:
    """Assembles the final RetrieverQueryEngine."""
    # Step 1: Initialize LLM if not provided
    if llm is None:
        llm = get_academic_llm(api_key=os.getenv("GROQ_API_KEY"))

    # Step 2: Fetch the academic prompt
    prompt_tmpl = get_academic_prompt()

    # Step 3: Instantiate response synthesizer
    synthesizer = get_response_synthesizer(
        llm=llm,
        text_qa_template=prompt_tmpl,
        response_mode=ResponseMode.COMPACT
    )

    # Step 4: Return the fully constructed RetrieverQueryEngine
    return RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=synthesizer,
        node_postprocessors=node_postprocessors
    )


def format_response_with_sources(response_object: Any) -> Dict[str, Any]:
    """Helper function to parse the LlamaIndex Response into a structured Dict."""
    sources = []

    # Loop over the source nodes that were retrieved and used for synthesis
    for node in response_object.source_nodes:
        meta = node.node.metadata
        sources.append({
            "node_id": node.node.node_id,
            "score": round(node.score, 4) if node.score else None,
            "file_name": meta.get("file_name", "Unknown File"),
            "page_number": meta.get("page_label", meta.get("page_number", "N/A")),
            "snippet": node.node.get_content()[:200] + "..."
        })

    return {
        "answer": str(response_object),
        "sources": sources
    }