"""Tests for the Hierarchical pattern.

All tests mock the LLM so they run without an API key and are fully
deterministic.
"""

import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langgraph.types import Send

from patterns.hierarchical.pattern import (
    HierarchicalPattern,
    HierarchicalState,
    WorkerState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    """Return a mock LLM whose ``.invoke()`` yields *responses* in order."""
    mock = MagicMock()
    if responses is None:
        mock.invoke.return_value = AIMessage(content="Mock output.")
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
        pattern = HierarchicalPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = HierarchicalPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "manager_decompose" in node_names
        assert "worker_invoker" in node_names
        assert "manager_aggregate" in node_names


class TestManagerDecompose:
    """Verify manager decomposition produces subtasks."""

    def test_decompose_returns_subtasks_list(self) -> None:
        mock_llm = _make_mock_llm([
            json.dumps([
                {"task_id": "subtask_0", "title": "Tech Analysis", "objective": "Analyze tech trends"},
                {"task_id": "subtask_1", "title": "Market Analysis", "objective": "Analyze market dynamics"},
            ])
        ])
        pattern = HierarchicalPattern(llm=mock_llm)
        state: HierarchicalState = {
            "task": "Analyze the AI industry",
            "num_workers": 3,
            "decomposed_tasks": [],
            "worker_results": [],
            "final_result": "",
        }
        output = pattern._manager_decompose(state)
        assert "decomposed_tasks" in output
        assert len(output["decomposed_tasks"]) == 2

    def test_decompose_includes_task_id_and_objective(self) -> None:
        subtasks = [
            {"task_id": "s0", "title": "T", "objective": "Objective 0"},
            {"task_id": "s1", "title": "T", "objective": "Objective 1"},
        ]
        mock_llm = _make_mock_llm([json.dumps(subtasks)])
        pattern = HierarchicalPattern(llm=mock_llm)
        output = pattern._manager_decompose({
            "task": "Test",
            "num_workers": 2,
            "decomposed_tasks": [],
            "worker_results": [],
            "final_result": "",
        })
        assert output["decomposed_tasks"][0]["task_id"] == "s0"
        assert output["decomposed_tasks"][1]["objective"] == "Objective 1"


class TestDispatchFanOut:
    """Verify that _dispatch produces the correct Send objects."""

    def test_dispatch_returns_one_send_per_subtask(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = HierarchicalPattern(llm=mock_llm)
        subtasks = [
            {"task_id": "s0", "title": "A", "objective": "Obj A"},
            {"task_id": "s1", "title": "B", "objective": "Obj B"},
            {"task_id": "s2", "title": "C", "objective": "Obj C"},
        ]
        state: HierarchicalState = {
            "task": "Test",
            "num_workers": 3,
            "decomposed_tasks": subtasks,
            "worker_results": [],
            "final_result": "",
        }
        sends = pattern._dispatch(state)
        assert len(sends) == 3

    def test_dispatch_send_targets_worker_invoker(self) -> None:
        pattern = HierarchicalPattern(llm=_make_mock_llm())
        sends = pattern._dispatch({
            "task": "t",
            "num_workers": 1,
            "decomposed_tasks": [{"task_id": "s0", "title": "T", "objective": "O"}],
            "worker_results": [],
            "final_result": "",
        })
        assert all(isinstance(s, Send) for s in sends)
        assert sends[0].node == "worker_invoker"

    def test_dispatch_send_contains_task_id_and_subtask(self) -> None:
        pattern = HierarchicalPattern(llm=_make_mock_llm())
        sends = pattern._dispatch({
            "task": "Test",
            "num_workers": 1,
            "decomposed_tasks": [{"task_id": "id_0", "title": "T", "objective": "The objective"}],
            "worker_results": [],
            "final_result": "",
        })
        payload = sends[0].arg
        assert payload["task_id"] == "id_0"
        assert payload["subtask"] == "The objective"

    def test_dispatch_empty_subtasks(self) -> None:
        pattern = HierarchicalPattern(llm=_make_mock_llm())
        sends = pattern._dispatch({
            "task": "t",
            "num_workers": 0,
            "decomposed_tasks": [],
            "worker_results": [],
            "final_result": "",
        })
        assert sends == []


class TestWorkerInvoker:
    """Verify worker invoker processes subtask and returns structured result."""

    def test_worker_invoker_returns_worker_result(self) -> None:
        mock_llm = _make_mock_llm(["Detailed analysis of the subtask."])
        pattern = HierarchicalPattern(llm=mock_llm)
        state: WorkerState = {
            "task_id": "s0",
            "subtask": "Analyze market trends",
            "reasoning_steps": [],
            "result": "",
        }
        output = pattern._worker_invoker(state)
        assert "worker_results" in output
        assert len(output["worker_results"]) == 1

    def test_worker_invoker_result_contains_task_id_subtask_and_output(self) -> None:
        analysis = "Market trends show 20% growth."
        mock_llm = _make_mock_llm([analysis])
        pattern = HierarchicalPattern(llm=mock_llm)
        state: WorkerState = {
            "task_id": "worker_1",
            "subtask": "Market analysis",
            "reasoning_steps": [],
            "result": "",
        }
        output = pattern._worker_invoker(state)
        result = output["worker_results"][0]
        assert result["task_id"] == "worker_1"
        assert result["subtask"] == "Market analysis"
        assert result["result"] == analysis


class TestManagerAggregate:
    """Verify manager aggregation synthesises worker results."""

    def test_aggregate_returns_final_result(self) -> None:
        synthesis = "The final synthesis across all workers shows..."
        mock_llm = _make_mock_llm([synthesis])
        pattern = HierarchicalPattern(llm=mock_llm)
        state: HierarchicalState = {
            "task": "AI Industry Analysis",
            "num_workers": 2,
            "decomposed_tasks": [],
            "worker_results": [
                {"task_id": "s0", "subtask": "Tech", "result": "Tech analysis", "reasoning": []},
                {"task_id": "s1", "subtask": "Market", "result": "Market analysis", "reasoning": []},
            ],
            "final_result": "",
        }
        output = pattern._manager_aggregate(state)
        assert output["final_result"] == synthesis

    def test_aggregate_includes_all_worker_results_in_prompt(self) -> None:
        mock_llm = _make_mock_llm(["final synthesis"])
        pattern = HierarchicalPattern(llm=mock_llm)
        state: HierarchicalState = {
            "task": "T",
            "num_workers": 2,
            "decomposed_tasks": [],
            "worker_results": [
                {"task_id": "s0", "subtask": "Sub-A", "result": "Result A", "reasoning": []},
                {"task_id": "s1", "subtask": "Sub-B", "result": "Result B", "reasoning": []},
            ],
            "final_result": "",
        }
        pattern._manager_aggregate(state)
        messages = mock_llm.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "Result A" in human_content
        assert "Result B" in human_content


class TestFullGraphExecution:
    """End-to-end test running the compiled graph with a mock LLM."""

    def test_full_run_with_two_workers(self) -> None:
        """Test full graph: decompose -> 2 workers -> aggregate."""
        mock_llm = _make_mock_llm([
            # Manager decompose
            json.dumps([
                {"task_id": "s0", "title": "Tech", "objective": "Analyze tech"},
                {"task_id": "s1", "title": "Market", "objective": "Analyze market"},
            ]),
            # Worker 1
            "Tech analysis: transformers dominate",
            # Worker 2
            "Market analysis: $18B VC funding",
            # Manager aggregate
            "Final synthesis: AI industry is strong",
        ])
        pattern = HierarchicalPattern(llm=mock_llm)
        result = pattern.run(task="Analyze AI industry")

        assert result["task"] == "Analyze AI industry"
        assert len(result["decomposed_tasks"]) == 2
        assert len(result["worker_results"]) == 2
        assert result["final_result"] == "Final synthesis: AI industry is strong"

    def test_full_run_results_contain_both_task_ids(self) -> None:
        mock_llm = _make_mock_llm([
            json.dumps([
                {"task_id": "A", "title": "T", "objective": "Task A"},
                {"task_id": "B", "title": "T", "objective": "Task B"},
            ]),
            "Result A",
            "Result B",
            "Synthesis",
        ])
        pattern = HierarchicalPattern(llm=mock_llm)
        result = pattern.run(task="Test task")
        result_ids = {r["task_id"] for r in result["worker_results"]}
        assert result_ids == {"A", "B"}

    def test_llm_called_correct_number_of_times(self) -> None:
        mock_llm = _make_mock_llm([
            json.dumps([{"task_id": "s", "title": "T", "objective": "O"}]),
            "worker_result",
            "final_synthesis",
        ])
        pattern = HierarchicalPattern(llm=mock_llm)
        pattern.run(task="Test")
        # 1 decompose + 1 worker + 1 aggregate = 3
        assert mock_llm.invoke.call_count == 3
