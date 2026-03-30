"""Tests for the MapReduce pattern.

All tests mock the LLM so they run without an API key and are fully
deterministic.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Send

from patterns.map_reduce.pattern import (
    MapReducePattern,
    MapReduceState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    """Return a mock LLM whose ``.invoke()`` yields *responses* in order.

    If *responses* is ``None`` a single generic reply is used for every call.
    """
    mock = MagicMock()
    if responses is None:
        mock.invoke.return_value = AIMessage(content="Mock analysis output.")
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
        pattern = MapReducePattern(llm=mock_llm)
        compiled = pattern.build_graph()
        # A compiled graph exposes an `invoke` method.
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = MapReducePattern(llm=mock_llm)
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        # LangGraph always adds __start__ and __end__ pseudo-nodes.
        assert "mapper" in node_names
        assert "reducer" in node_names


class TestDispatchFanOut:
    """Verify that ``_dispatch`` produces the correct Send objects."""

    def test_dispatch_returns_correct_number_of_sends(self) -> None:
        pattern = MapReducePattern(llm=_make_mock_llm())
        sources = ["src_a", "src_b", "src_c"]
        state: MapReduceState = {
            "topic": "test topic",
            "sources": sources,
            "results": [],
            "final_summary": "",
        }
        sends = pattern._dispatch(state)
        assert len(sends) == 3

    def test_dispatch_send_targets_mapper(self) -> None:
        pattern = MapReducePattern(llm=_make_mock_llm())
        state: MapReduceState = {
            "topic": "t",
            "sources": ["only_one"],
            "results": [],
            "final_summary": "",
        }
        sends = pattern._dispatch(state)
        assert all(isinstance(s, Send) for s in sends)
        assert sends[0].node == "mapper"

    def test_dispatch_send_contains_source_and_topic(self) -> None:
        pattern = MapReducePattern(llm=_make_mock_llm())
        state: MapReduceState = {
            "topic": "AI trends",
            "sources": ["Reuters"],
            "results": [],
            "final_summary": "",
        }
        sends = pattern._dispatch(state)
        payload = sends[0].arg
        assert payload["source"] == "Reuters"
        assert payload["topic"] == "AI trends"

    def test_dispatch_empty_sources(self) -> None:
        pattern = MapReducePattern(llm=_make_mock_llm())
        state: MapReduceState = {
            "topic": "t",
            "sources": [],
            "results": [],
            "final_summary": "",
        }
        sends = pattern._dispatch(state)
        assert sends == []


class TestMapperSingleSource:
    """Verify mapper node processes a single source correctly."""

    def test_mapper_returns_result_list(self) -> None:
        mock_llm = _make_mock_llm(["Deep analysis of Reuters data."])
        pattern = MapReducePattern(llm=mock_llm)
        worker_state = {"source": "Reuters: Trade report", "topic": "Global trade"}
        output = pattern._mapper(worker_state)

        assert "results" in output
        assert len(output["results"]) == 1

    def test_mapper_result_contains_source_and_analysis(self) -> None:
        analysis_text = "The semiconductor market shows strong growth."
        mock_llm = _make_mock_llm([analysis_text])
        pattern = MapReducePattern(llm=mock_llm)
        worker_state = {"source": "Bloomberg: Chips", "topic": "Semiconductors"}
        output = pattern._mapper(worker_state)

        result = output["results"][0]
        assert result["source"] == "Bloomberg: Chips"
        assert result["analysis"] == analysis_text

    def test_mapper_invokes_llm_with_correct_messages(self) -> None:
        mock_llm = _make_mock_llm(["ok"])
        pattern = MapReducePattern(llm=mock_llm)
        pattern._mapper({"source": "TechCrunch: AI", "topic": "AI funding"})

        mock_llm.invoke.assert_called_once()
        messages = mock_llm.invoke.call_args[0][0]
        # First message is system prompt, second is human prompt
        assert len(messages) == 2
        assert "AI funding" in messages[1].content
        assert "TechCrunch: AI" in messages[1].content


class TestReducerCombinesResults:
    """Verify reducer synthesises multiple analyses."""

    def test_reducer_produces_final_summary(self) -> None:
        summary_text = "Overall, AI is transforming multiple sectors."
        mock_llm = _make_mock_llm([summary_text])
        pattern = MapReducePattern(llm=mock_llm)

        state: MapReduceState = {
            "topic": "AI overview",
            "sources": ["A", "B"],
            "results": [
                {"source": "A", "analysis": "Analysis of A"},
                {"source": "B", "analysis": "Analysis of B"},
            ],
            "final_summary": "",
        }
        output = pattern._reducer(state)
        assert output["final_summary"] == summary_text

    def test_reducer_includes_all_analyses_in_prompt(self) -> None:
        mock_llm = _make_mock_llm(["synthesis"])
        pattern = MapReducePattern(llm=mock_llm)

        state: MapReduceState = {
            "topic": "topic",
            "sources": ["X", "Y", "Z"],
            "results": [
                {"source": "X", "analysis": "xa"},
                {"source": "Y", "analysis": "ya"},
                {"source": "Z", "analysis": "za"},
            ],
            "final_summary": "",
        }
        pattern._reducer(state)

        messages = mock_llm.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "xa" in human_content
        assert "ya" in human_content
        assert "za" in human_content
        assert "3" in human_content  # mentions the count


class TestFullGraphExecution:
    """End-to-end test running the compiled graph with a mock LLM."""

    def test_full_run_with_three_sources(self) -> None:
        sources = [
            "Source Alpha: Details on topic",
            "Source Beta: More info on topic",
            "Source Gamma: Additional perspective",
        ]
        # The LLM will be called 3 times for mappers + 1 time for reducer = 4
        responses = [
            "Alpha analysis paragraph.",
            "Beta analysis paragraph.",
            "Gamma analysis paragraph.",
            "Final synthesized summary combining all three sources.",
        ]
        mock_llm = _make_mock_llm(responses)
        pattern = MapReducePattern(llm=mock_llm)

        result = pattern.run(topic="Test Topic", sources=sources)

        # Verify structure
        assert result["topic"] == "Test Topic"
        assert len(result["sources"]) == 3
        assert len(result["results"]) == 3
        assert result["final_summary"] == "Final synthesized summary combining all three sources."

    def test_full_run_results_contain_correct_sources(self) -> None:
        sources = ["A: info", "B: info", "C: info"]
        responses = ["a_out", "b_out", "c_out", "summary"]
        mock_llm = _make_mock_llm(responses)
        pattern = MapReducePattern(llm=mock_llm)

        result = pattern.run(topic="T", sources=sources)

        result_sources = {r["source"] for r in result["results"]}
        assert result_sources == set(sources)

    def test_full_run_single_source(self) -> None:
        """Even with one source the fan-out/reduce pipeline works."""
        mock_llm = _make_mock_llm(["single analysis", "single summary"])
        pattern = MapReducePattern(llm=mock_llm)

        result = pattern.run(topic="Solo", sources=["Only source"])

        assert len(result["results"]) == 1
        assert result["final_summary"] == "single summary"

    def test_llm_called_correct_number_of_times(self) -> None:
        sources = ["s1", "s2", "s3"]
        mock_llm = _make_mock_llm(
            ["a1", "a2", "a3", "final"]
        )
        pattern = MapReducePattern(llm=mock_llm)
        pattern.run(topic="T", sources=sources)

        # 3 mapper calls + 1 reducer call = 4
        assert mock_llm.invoke.call_count == 4
