from typing import List, Tuple
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core import Document
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.schema import BaseNode

from .cleaner import ArtifactCleaner


def build_pipeline() -> IngestionPipeline:
    cleaner = ArtifactCleaner()
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[2048, 512, 128]
    )
    pipeline = IngestionPipeline(
        transformations=[cleaner, node_parser]
    )
    return pipeline


def run_ingestion(documents: List[Document]) -> Tuple[List[BaseNode], List[BaseNode]]:
    pipeline = build_pipeline()
    allnodes = pipeline.run(documents=documents)
    leafnodes = get_leaf_nodes(allnodes)
    return allnodes, leafnodes