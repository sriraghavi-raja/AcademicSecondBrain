from typing import List, Tuple
from llama_index.core import VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.retrievers.bm25 import BM25Retriever


class FastHybridRetriever(BaseRetriever):
    """Combines Vector and BM25 retrievers with zero LLM overhead."""
    def __init__(self, vector_retriever: BaseRetriever, bm25_retriever: BaseRetriever):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        vec_nodes = self.vector_retriever.retrieve(query_bundle)
        bm25_nodes = self.bm25_retriever.retrieve(query_bundle)

        # Fast deduplication by node_id
        seen_ids = set()
        combined_nodes = []
        for node in vec_nodes + bm25_nodes:
            if node.node.node_id not in seen_ids:
                seen_ids.add(node.node.node_id)
                combined_nodes.append(node)

        return combined_nodes

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        vec_nodes = await self.vector_retriever.aretrieve(query_bundle)
        bm25_nodes = await self.bm25_retriever.aretrieve(query_bundle)

        seen_ids = set()
        combined_nodes = []
        for node in vec_nodes + bm25_nodes:
            if node.node.node_id not in seen_ids:
                seen_ids.add(node.node.node_id)
                combined_nodes.append(node)

        return combined_nodes


class AcademicRetrieverWrapper(BaseRetriever):
    """Wraps the full retriever stack and exposes safe internal updates."""
    def __init__(self, hybrid_retriever: FastHybridRetriever, auto_merging_retriever: AutoMergingRetriever):
        self.hybrid_retriever = hybrid_retriever
        self.auto_merging_retriever = auto_merging_retriever
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return self.auto_merging_retriever.retrieve(query_bundle)

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return await self.auto_merging_retriever.aretrieve(query_bundle)

    def update_bm25(self, new_bm25_retriever: BaseRetriever):
        """Safely updates the BM25 retriever in the underlying stack."""
        self.hybrid_retriever.bm25_retriever = new_bm25_retriever


def build_retriever_stack(index: VectorStoreIndex) -> Tuple[AcademicRetrieverWrapper, List[BaseNodePostprocessor]]:
    """
    Constructs the retriever stack ONCE.
    Call this during application startup or index loading, NOT per query request!
    """
    # 1. Reduced top_k from 25 -> 12 to halve candidate workload
    vector_retriever = index.as_retriever(similarity_top_k=12)

    # 2. Build BM25 index ONCE (similarity_top_k=12)
    bm25_retriever = BM25Retriever.from_defaults(
        docstore=index.storage_context.docstore,
        similarity_top_k=12
    )

    # 3. Pure LLM-free hybrid fusion
    hybrid_retriever = FastHybridRetriever(vector_retriever, bm25_retriever)

    # 4. Auto-Merging Retriever (threshold tuned to 0.4 for faster decision making)
    auto_merging_retriever = AutoMergingRetriever(
        hybrid_retriever,
        storage_context=index.storage_context,
        simple_ratio_thresh=0.4
    )

    # 5. Wrapper class to manage retriever state cleanly
    academic_retriever = AcademicRetrieverWrapper(hybrid_retriever, auto_merging_retriever)

    # 6. Cross-Encoder Reranker (processes top ~20 merged candidates down to top 5)
    reranker = SentenceTransformerRerank(
        model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_n=5,
    )

    return academic_retriever, [reranker]