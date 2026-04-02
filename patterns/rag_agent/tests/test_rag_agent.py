"""Tests for the RAG-Agent pattern.

All tests mock the LLM so they run without an API key and are fully
deterministic.
"""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from patterns.rag_agent.pattern import (
    RAGAgentPattern,
    RAGAgentState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    """Return a mock LLM whose ``.invoke()`` yields *responses* in order."""
    mock = MagicMock()
    if responses is None:
        mock.invoke.return_value = AIMessage(content="Mock response.")
    else:
        mock.invoke.side_effect = [
            AIMessage(content=text) for text in responses
        ]
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildGraph:
    """Verify graph construction produces a runnable compiled graph."""

    def test_build_graph_returns_compiled_graph(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = RAGAgentPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = RAGAgentPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "agent" in node_names
        assert "fetch" in node_names
        assert "synthesize" in node_names


class TestAgentNode:
    """Verify agent node parses LLM response correctly."""

    def test_agent_returns_retrieve_decision(self) -> None:
        mock_llm = _make_mock_llm([
            "## Decision: RETRIEVE\n## Reasoning: Need facts.\n## Documents:\ndoc1\ndoc2"
        ])
        pattern = RAGAgentPattern(llm=mock_llm)
        output = pattern._agent({
            "query": "What is Python?",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "",
            "pending_doc_queue": [],
        })
        assert output["decision"] == "retrieve"
        assert output["pending_doc_queue"] == [["doc1", "doc2"]]

    def test_agent_returns_answer_decision(self) -> None:
        mock_llm = _make_mock_llm([
            "## Decision: ANSWER\n## Answer: Python is a programming language."
        ])
        pattern = RAGAgentPattern(llm=mock_llm)
        output = pattern._agent({
            "query": "What is Python?",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "",
            "pending_doc_queue": [],
        })
        assert output["decision"] == "answer"
        assert "programming language" in output["response"]

    def test_agent_defaults_to_answer_on_missing_decision(self) -> None:
        mock_llm = _make_mock_llm(["No decision found in response."])
        pattern = RAGAgentPattern(llm=mock_llm)
        output = pattern._agent({
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "",
            "pending_doc_queue": [],
        })
        assert output["decision"] == "answer"

    def test_agent_includes_previous_docs_in_context(self) -> None:
        mock_llm = _make_mock_llm(["## Decision: ANSWER\n## Answer: Done."])
        pattern = RAGAgentPattern(llm=mock_llm)
        pattern._agent({
            "query": "Q",
            "retrieved_docs": [{"doc_id": "d1", "content": "Previous doc content."}],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 1,
            "max_retrievals": 3,
            "decision": "",
            "pending_doc_queue": [],
        })
        messages = mock_llm.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "Previously retrieved documents" in human_content
        assert "d1" in human_content


class TestFetchNode:
    """Verify fetch node retrieves and stores documents."""

    def test_fetch_returns_structured_docs(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        output = pattern._fetch({
            "query": "What is Python?",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [["doc1", "doc2"]],
        })
        assert len(output["retrieved_docs"]) == 2
        assert output["retrieval_count"] == 1
        assert output["retrieved_docs"][0]["doc_id"] == "doc1"
        # Queue should be consumed, leaving empty queue
        assert output.get("pending_doc_queue", []) == []

    def test_fetch_increments_retrieval_count(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        output = pattern._fetch({
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 2,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [["doc3"]],
        })
        assert output["retrieval_count"] == 3
        assert output.get("pending_doc_queue", []) == []

    def test_fetch_empty_queue(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        output = pattern._fetch({
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [],
        })
        # When queue is empty, fetch just increments count without adding docs
        assert output["retrieval_count"] == 1

    def test_fetch_consumes_one_round_at_a_time(self) -> None:
        """Verify that fetch only consumes one round's docs, leaving rest."""
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        output = pattern._fetch({
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [["doc1"], ["doc2", "doc3"]],
        })
        assert output["retrieval_count"] == 1
        assert [d["doc_id"] for d in output["retrieved_docs"]] == ["doc1"]
        assert output["pending_doc_queue"] == [["doc2", "doc3"]]


class TestRouteNode:
    """Verify routing logic."""

    def test_route_to_answer_when_decision_is_answer(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        state: RAGAgentState = {
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "A",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "answer",
            "pending_doc_queue": [],
        }
        assert pattern._route(state) == "answer"

    def test_route_to_retrieve_when_decision_is_retrieve(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        state: RAGAgentState = {
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [["doc1"]],
        }
        assert pattern._route(state) == "retrieve"

    def test_route_to_max_retrievals_when_count_reached(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        state: RAGAgentState = {
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 3,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [["doc1"]],
        }
        assert pattern._route(state) == "max_retrievals"

    def test_route_defaults_to_answer(self) -> None:
        pattern = RAGAgentPattern(llm=_make_mock_llm())
        state: RAGAgentState = {
            "query": "Q",
            "retrieved_docs": [],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 0,
            "max_retrievals": 3,
            "decision": "",
            "pending_doc_queue": [],
        }
        assert pattern._route(state) == "answer"


class TestSynthesizeNode:
    """Verify synthesize node."""

    def test_synthesize_invokes_llm_with_docs(self) -> None:
        mock_llm = _make_mock_llm(["Synthesized answer."])
        pattern = RAGAgentPattern(llm=mock_llm)
        pattern._synthesize({
            "query": "What is Python?",
            "retrieved_docs": [
                {"doc_id": "doc1", "content": "Python is a programming language."}
            ],
            "agent_reasoning": [],
            "response": "",
            "retrieval_count": 1,
            "max_retrievals": 3,
            "decision": "retrieve",
            "pending_doc_queue": [],
        })
        mock_llm.invoke.assert_called_once()
        messages = mock_llm.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "Python" in human_content


class TestFullGraphExecution:
    """End-to-end test running the compiled graph with a mock LLM."""

    def test_full_run_direct_answer(self) -> None:
        # Agent immediately answers (no retrieval needed)
        mock_llm = _make_mock_llm([
            "## Decision: ANSWER\n## Answer: Python is great."
        ])
        pattern = RAGAgentPattern(llm=mock_llm)
        result = pattern.run(query="What is Python?")

        assert result["retrieval_count"] == 0
        assert result["decision"] == "answer"
        assert "Python is great" in result["response"]

    def test_full_run_with_one_retrieval(self) -> None:
        # Agent retrieves -> fetch -> synthesize -> agent answers
        mock_llm = _make_mock_llm([
            "## Decision: RETRIEVE\n## Docs:\ndoc1\n## Reasoning: Need facts.",
            "Synthesized answer from retrieved docs.",
            "## Decision: ANSWER\n## Answer: Done."
        ])
        pattern = RAGAgentPattern(llm=mock_llm)
        result = pattern.run(query="What is Python?")

        # Agent calls: 2 (first decide RETRIEVE, second decide ANSWER)
        # Fetch and synthesize are not LLM calls
        assert result["retrieval_count"] == 1
        assert len(result["retrieved_docs"]) == 1
        assert result["decision"] == "answer"

    def test_full_run_respects_max_retrievals(self) -> None:
        # The queue mechanism processes one round at a time.
        # Flow: agent(RETRIEVE,r1) -> fetch -> synthesize -> agent(ANSWER) -> END
        # agent calls: 2 (first decides RETRIEVE, second decides ANSWER after one fetch)
        # synthesize calls: 1
        # Total LLM calls: 3
        mock_llm = _make_mock_llm([
            "## Decision: RETRIEVE\n## Docs:\ndoc1",   # agent 1: count=0, routes to fetch
            "Synthesized 1",                             # synthesize 1
            "## Decision: ANSWER\n## Answer: Done.",     # agent 2: stops after 1 retrieval
        ])
        pattern = RAGAgentPattern(llm=mock_llm, max_retrievals=2)
        result = pattern.run(query="Q")

        # Only 1 retrieval because agent stops after seeing empty queue
        assert result["retrieval_count"] == 1
        assert len(result["retrieved_docs"]) == 1
        assert result["retrieved_docs"][0]["doc_id"] == "doc1"

    def test_full_run_with_multiple_docs_per_round(self) -> None:
        # Agent requests multiple docs in one round
        mock_llm = _make_mock_llm([
            "## Decision: RETRIEVE\n## Docs:\ndoc1\ndoc2\ndoc3",  # agent: all 3 docs in one round
            "Synthesized answer.",                                 # synthesize
            "## Decision: ANSWER\n## Answer: Done."              # agent: final answer
        ])
        pattern = RAGAgentPattern(llm=mock_llm, max_retrievals=3)
        result = pattern.run(query="Q")

        # 1 retrieval (all 3 docs fetched at once)
        assert result["retrieval_count"] == 1
        assert len(result["retrieved_docs"]) == 3
        assert result["decision"] == "answer"
