import threading
from typing import Dict, List, Optional
from llama_index.core import VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.retrievers.bm25 import BM25Retriever

from src.rag.ingestion.metadata import OWNER_KEY


class FastHybridRetriever(BaseRetriever):
    """Combines Vector and BM25 retrievers with zero LLM overhead."""
    def __init__(self, vector_retriever: BaseRetriever, bm25_retriever: Optional[BaseRetriever] = None):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        vec_nodes = self.vector_retriever.retrieve(query_bundle)
        bm25_nodes = self.bm25_retriever.retrieve(query_bundle) if self.bm25_retriever else []
        return self._deduplicate(vec_nodes + bm25_nodes)

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        vec_nodes = await self.vector_retriever.aretrieve(query_bundle)
        bm25_nodes = await self.bm25_retriever.aretrieve(query_bundle) if self.bm25_retriever else []
        return self._deduplicate(vec_nodes + bm25_nodes)

    @staticmethod
    def _deduplicate(nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        # Fast deduplication by node_id
        seen_ids = set()
        combined_nodes = []
        for node in nodes:
            if node.node.node_id not in seen_ids:
                seen_ids.add(node.node.node_id)
                combined_nodes.append(node)
        return combined_nodes


class RetrieverFactory:
    """
    Builds retrievers that can only ever see one user's nodes.

    Vector search filters on the owner metadata. BM25 is built from an explicit list of the user's nodes,
    never with BM25Retriever(filters=...): that only masks scores, so other owners' nodes still come back
    with a score of zero as padding.
    """

    def __init__(self, index: VectorStoreIndex, similarity_top_k: int = 12, merge_ratio: float = 0.4):
        self.index = index
        self.similarity_top_k = similarity_top_k
        self.merge_ratio = merge_ratio
        self._bm25_by_user: Dict[str, Optional[BM25Retriever]] = {}
        self._lock = threading.Lock()

    def for_user(self, user_id: str) -> BaseRetriever:
        """Builds the hybrid + auto-merging retriever for one user. Cheap: BM25 is cached per user."""
        owner_filter = MetadataFilters(
            filters=[MetadataFilter(key=OWNER_KEY, value=user_id, operator=FilterOperator.EQ)]
        )
        vector_retriever = self.index.as_retriever(similarity_top_k=self.similarity_top_k, filters=owner_filter)
        hybrid_retriever = FastHybridRetriever(vector_retriever, self.bm25_for(user_id))
        return AutoMergingRetriever(
            hybrid_retriever,
            storage_context=self.index.storage_context,
            simple_ratio_thresh=self.merge_ratio
        )

    def bm25_for(self, user_id: str) -> Optional[BM25Retriever]:
        """The user's cached BM25 retriever, or None while the user has no documents."""
        with self._lock:
            if user_id not in self._bm25_by_user:
                self._bm25_by_user[user_id] = self._build_bm25(user_id)
            return self._bm25_by_user[user_id]

    def invalidate(self, user_id: str) -> None:
        """Forgets the user's cached BM25. Call after every upload or delete that changes their nodes."""
        with self._lock:
            self._bm25_by_user.pop(user_id, None)

    def _build_bm25(self, user_id: str) -> Optional[BM25Retriever]:
        nodes = [node for node in self.index.docstore.docs.values() if node.metadata.get(OWNER_KEY) == user_id]
        if not nodes:
            return None
        return BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=self.similarity_top_k)


def build_postprocessors() -> List[BaseNodePostprocessor]:
    """Cross-Encoder Reranker (processes the merged candidates down to the top 5). Stateless, so shared."""
    return [
        SentenceTransformerRerank(
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            top_n=5,
        )
    ]
