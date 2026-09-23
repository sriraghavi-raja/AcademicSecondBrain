"""Tools the chat agent can call, built fresh for each request around one user's own retriever."""

import os
from typing import Any, FrozenSet, List, Optional, Tuple

from llama_index.core.schema import QueryBundle
from llama_index.core.tools import FunctionTool

from src.rag.ingestion.metadata import FILE_KEY

# HierarchicalNodeParser's chunk_sizes are TOKENS (SentenceSplitter(chunk_size=...)), not characters,
# so a single auto-merged node can legitimately run several thousand characters. A flat per-node
# character cap silently sliced content mid-fact (a real bug: the exact detail a question asked
# about landed just past the cutoff). Instead, results are included in FULL, one at a time, until a
# total character budget is used up — the top result is always included whole even if it alone
# exceeds the budget, so the single most relevant match is never dropped or cut short.
TOTAL_CONTEXT_BUDGET_CHARS = int(os.getenv("SEARCH_CONTEXT_BUDGET_CHARS", "24000"))
MAX_RESULTS_SHOWN = 8


def build_document_tools(
    retriever: Any,
    document_titles: List[str],
    allowed_document_ids: Optional[FrozenSet[str]] = None,
    postprocessors: Optional[List[Any]] = None,
) -> Tuple[List[FunctionTool], List[dict]]:
    """
    Builds the agent's document tools around an already user-scoped retriever.

    retriever must already be scoped to one user (RetrieverFactory.for_user), so a search can never
    cross into another user's documents. allowed_document_ids, if given, must already be validated as
    that same user's own documents (see document_scope.validate_document_ids) — this function trusts
    it and only narrows results to those ids, it does not re-check ownership. postprocessors (e.g. the
    cross-encoder reranker) run on every search, the same as they always did for the older fixed
    pipeline in chat.py — agent mode must not silently skip them.

    Returns (tools, sources): sources is a list this call's search results get appended to, so the
    caller can build the existing `sources` SSE event once the agent finishes.
    """
    sources: List[dict] = []

    def search_documents(query: str) -> str:
        """Search the student's own uploaded documents for passages relevant to the query."""
        nodes = retriever.retrieve(query)
        if postprocessors:
            query_bundle = QueryBundle(query)
            for postprocessor in postprocessors:
                nodes = postprocessor.postprocess_nodes(nodes, query_bundle=query_bundle)
        if allowed_document_ids is not None:
            nodes = [node for node in nodes if node.node.metadata.get(FILE_KEY) in allowed_document_ids]
        if not nodes:
            return "No matching passages were found in the student's documents."

        lines = []
        used_chars = 0
        for node in nodes[:MAX_RESULTS_SHOWN]:
            text = node.node.get_content()
            if lines and used_chars + len(text) > TOTAL_CONTEXT_BUDGET_CHARS:
                break  # keep what already fit, in full; never cut this result in half to squeeze it in
            meta = node.node.metadata
            source = {
                "file": meta.get("file_name", "Unknown"),
                "page": meta.get("page_label", meta.get("page_number", "N/A")),
                "score": float(node.score) if node.score is not None else None,
            }
            sources.append(source)
            used_chars += len(text)
            lines.append(f"[{source['file']} p.{source['page']}] {text}")
        return "\n\n".join(lines)

    def list_documents() -> str:
        """List the titles of the student's own uploaded documents."""
        if not document_titles:
            return "The student has not uploaded any documents yet."
        return "\n".join(f"- {title}" for title in document_titles)

    tools = [
        FunctionTool.from_defaults(fn=search_documents, name="search_documents"),
        FunctionTool.from_defaults(fn=list_documents, name="list_documents"),
    ]
    return tools, sources
