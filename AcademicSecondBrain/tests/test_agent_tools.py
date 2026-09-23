import unittest
from types import SimpleNamespace

from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

from src.rag.registry import documents as document_registry
from src.rag.synthesis.agent_tools import TOTAL_CONTEXT_BUDGET_CHARS, build_document_tools
from src.rag.synthesis.document_scope import DocumentAccessError, validate_document_ids
from tests.support import GRANITE, ORCHID, IndexedTestCase, article


def call(tool, **kwargs):
    """Invokes a FunctionTool the way the agent does, and returns its plain string output."""
    return tool.call(**kwargs).raw_output


def find(tools, name):
    return next(tool for tool in tools if tool.metadata.name == name)


def scored_node(text, file_name="a.pdf", score=1.0, **metadata):
    node = TextNode(text=text, metadata={"file_name": file_name, **metadata})
    return NodeWithScore(node=node, score=score)


class BuildDocumentToolsTests(IndexedTestCase):
    def test_search_only_ever_sees_the_scoped_retrievers_own_documents(self):
        self.upload("alice", "alice.txt", article(ORCHID))
        self.upload("bob", "bob.txt", article(GRANITE))
        retriever = self.factory.for_user("alice")
        tools, sources = build_document_tools(retriever, ["alice.txt"])

        result = call(find(tools, "search_documents"), query=f"{ORCHID} {GRANITE}")

        self.assertIn("alice.txt", result)
        self.assertNotIn(GRANITE, result)
        self.assertTrue(sources)
        self.assertTrue(all(source["file"] == "alice.txt" for source in sources))

    def test_a_user_with_no_matching_documents_gets_an_honest_answer_not_an_error(self):
        retriever = self.factory.for_user("nobody")
        tools, sources = build_document_tools(retriever, [])

        result = call(find(tools, "search_documents"), query=ORCHID)

        self.assertIn("No matching passages", result)
        self.assertEqual(sources, [])

    def test_allowed_document_ids_narrows_search_to_just_those_documents(self):
        keep = self.upload("alice", "one.txt", article(ORCHID))["document_id"]
        self.upload("alice", "two.txt", article(GRANITE))
        retriever = self.factory.for_user("alice")

        tools, sources = build_document_tools(
            retriever, ["one.txt", "two.txt"], allowed_document_ids=frozenset({keep})
        )
        result = call(find(tools, "search_documents"), query=f"{ORCHID} {GRANITE}")

        self.assertNotIn(GRANITE, result)
        self.assertTrue(sources)
        self.assertTrue(all(source["file"] == "one.txt" for source in sources))

    def test_sources_accumulate_across_multiple_calls_within_one_turn(self):
        self.upload("alice", "a.txt", article(ORCHID))
        self.upload("alice", "b.txt", article(GRANITE))
        retriever = self.factory.for_user("alice")
        tools, sources = build_document_tools(retriever, ["a.txt", "b.txt"])
        search = find(tools, "search_documents")

        call(search, query=ORCHID)
        after_first_call = len(sources)
        call(search, query=GRANITE)

        self.assertGreater(after_first_call, 0)
        self.assertGreater(len(sources), after_first_call)

    def test_list_documents_reports_the_given_titles_or_says_there_are_none(self):
        retriever = self.factory.for_user("alice")

        tools, _ = build_document_tools(retriever, ["a.pdf", "b.pdf"])
        listing = call(find(tools, "list_documents"))
        self.assertIn("a.pdf", listing)
        self.assertIn("b.pdf", listing)

        empty_tools, _ = build_document_tools(retriever, [])
        self.assertIn("not uploaded", call(find(empty_tools, "list_documents")).lower())


class SearchDocumentsTruncationTests(unittest.TestCase):
    """Regression tests for a real bug: content past the old flat 400-char cap was silently cut,
    including the exact facts a question asked about. HierarchicalNodeParser's chunk_sizes are
    TOKENS, not characters (SentenceSplitter(chunk_size=...)), so a single auto-merged node can
    legitimately run several thousand characters — a small flat per-node cap was never safe.
    """

    def test_content_far_past_the_old_400_char_cutoff_still_reaches_the_model(self):
        # Mirrors the real failure: the answer sits after ~1300 characters of unrelated text.
        text = ("Unrelated filler. " * 80) + "The unique identifier is RAG-TEST-84721."
        retriever = SimpleNamespace(retrieve=lambda query: [scored_node(text)])
        tools, sources = build_document_tools(retriever, ["a.pdf"])

        result = call(find(tools, "search_documents"), query="identifier")

        self.assertIn("RAG-TEST-84721", result)
        self.assertEqual(sources, [{"file": "a.pdf", "page": "N/A", "score": 1.0}])

    def test_a_node_is_never_cut_off_mid_content(self):
        text = "A" * 5000 + "END-OF-NODE-MARKER"
        retriever = SimpleNamespace(retrieve=lambda query: [scored_node(text)])
        tools, _ = build_document_tools(retriever, ["a.pdf"])

        result = call(find(tools, "search_documents"), query="marker")

        self.assertIn("END-OF-NODE-MARKER", result)

    def test_the_single_top_result_is_always_included_in_full_even_if_it_alone_exceeds_the_budget(self):
        huge_text = "X" * (TOTAL_CONTEXT_BUDGET_CHARS * 2) + "MARKER-AT-THE-VERY-END"
        retriever = SimpleNamespace(retrieve=lambda query: [scored_node(huge_text)])
        tools, _ = build_document_tools(retriever, ["a.pdf"])

        result = call(find(tools, "search_documents"), query="marker")

        self.assertIn("MARKER-AT-THE-VERY-END", result)

    def test_results_beyond_the_total_budget_are_dropped_whole_not_truncated(self):
        first = scored_node("F" * (TOTAL_CONTEXT_BUDGET_CHARS - 100) + "FIRST-MARKER", score=0.9)
        second = scored_node("SECOND-MARKER " * 50, file_name="b.pdf", score=0.8)
        retriever = SimpleNamespace(retrieve=lambda query: [first, second])
        tools, sources = build_document_tools(retriever, ["a.pdf", "b.pdf"])

        result = call(find(tools, "search_documents"), query="marker")

        self.assertIn("FIRST-MARKER", result)
        self.assertNotIn("SECOND-MARKER", result)
        self.assertEqual(len(sources), 1)  # the dropped node never contributes a partial source either


class RerankerWiringTests(unittest.TestCase):
    """A real regression found while investigating: engine mode always applied the cross-encoder
    reranker (RagService.postprocessors); agent mode silently never did.
    """

    def test_given_postprocessors_are_applied_to_every_search(self):
        nodes = [scored_node("first", score=0.1), scored_node("second", score=0.2)]
        retriever = SimpleNamespace(retrieve=lambda query: nodes)
        calls = []

        class RecordingPostprocessor:
            def postprocess_nodes(self, candidate_nodes, query_bundle):
                calls.append((list(candidate_nodes), query_bundle.query_str))
                return list(reversed(candidate_nodes))  # prove the (possibly reordered) result is used

        tools, sources = build_document_tools(
            retriever, ["a.pdf"], postprocessors=[RecordingPostprocessor()]
        )
        call(find(tools, "search_documents"), query="my query")

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], nodes)
        self.assertEqual(calls[0][1], "my query")
        self.assertEqual([source["score"] for source in sources], [0.2, 0.1])  # reversed order was used

    def test_no_postprocessors_means_the_raw_retriever_order_is_used_unchanged(self):
        nodes = [scored_node("first", score=0.1), scored_node("second", score=0.2)]
        retriever = SimpleNamespace(retrieve=lambda query: nodes)

        tools, sources = build_document_tools(retriever, ["a.pdf"])
        call(find(tools, "search_documents"), query="q")

        self.assertEqual([source["score"] for source in sources], [0.1, 0.2])


class ValidateDocumentIdsTests(IndexedTestCase):
    def test_none_or_empty_means_no_restriction(self):
        self.assertIsNone(validate_document_ids("alice", None))
        self.assertIsNone(validate_document_ids("alice", []))

    def test_the_callers_own_ready_document_is_accepted(self):
        document_id = self.upload("alice", "a.txt", article(ORCHID))["document_id"]

        self.assertEqual(validate_document_ids("alice", [document_id]), frozenset({document_id}))

    def test_a_foreign_or_unknown_document_is_rejected(self):
        alice_document = self.upload("alice", "a.txt", article(ORCHID))["document_id"]

        with self.assertRaises(DocumentAccessError):
            validate_document_ids("bob", [alice_document])
        with self.assertRaises(DocumentAccessError):
            validate_document_ids("alice", ["no-such-document"])

    def test_a_document_still_processing_is_not_yet_usable(self):
        document_registry.create_document("still-processing", "alice", "a.pdf", "stored", "hash", 10)

        with self.assertRaises(DocumentAccessError):
            validate_document_ids("alice", ["still-processing"])


if __name__ == "__main__":
    unittest.main()
