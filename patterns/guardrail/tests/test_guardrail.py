"""Tests for the GuardRail pattern.

All tests mock the LLM so they run without an API key and are fully
deterministic.
"""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from patterns.guardrail.pattern import (
    GuardRailPattern,
    GuardRailState,
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
        pattern = GuardRailPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = GuardRailPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "primary_execute" in node_names
        assert "guard_check" in node_names
        assert "finalize" in node_names


class TestPrimaryExecute:
    """Verify primary execution node."""

    def test_primary_increments_attempt_count(self) -> None:
        mock_llm = _make_mock_llm(["Generated content."])
        pattern = GuardRailPattern(llm=mock_llm)
        state: GuardRailState = {
            "task": "Write about AI",
            "primary_output": "",
            "guard_verdict": "",
            "guard_feedback": "",
            "attempts": 0,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        output = pattern._primary_execute(state)
        assert output["attempts"] == 1
        assert output["primary_output"] == "Generated content."

    def test_primary_uses_feedback_in_retry(self) -> None:
        mock_llm = _make_mock_llm(["Improved content."])
        pattern = GuardRailPattern(llm=mock_llm)
        state: GuardRailState = {
            "task": "Write about AI",
            "primary_output": "Old content",
            "guard_verdict": "redirect",
            "guard_feedback": "Please be more specific about transformers.",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        pattern._primary_execute(state)
        messages = mock_llm.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "transformers" in human_content
        assert "Previous feedback" in human_content

    def test_primary_first_attempt_no_feedback(self) -> None:
        mock_llm = _make_mock_llm(["First content."])
        pattern = GuardRailPattern(llm=mock_llm)
        state: GuardRailState = {
            "task": "Write about AI",
            "primary_output": "",
            "guard_verdict": "",
            "guard_feedback": "",
            "attempts": 0,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        pattern._primary_execute(state)
        messages = mock_llm.invoke.call_args[0][0]
        assert "Previous feedback" not in messages[1].content


class TestGuardCheck:
    """Verify guard check node parses verdict correctly."""

    def test_guard_parses_approve_verdict(self) -> None:
        mock_llm = _make_mock_llm([
            "## Verdict: APPROVE\n## Feedback: Output looks good."
        ])
        pattern = GuardRailPattern(llm=mock_llm)
        output = pattern._guard_check({
            "task": "T",
            "primary_output": "Generated text",
            "guard_verdict": "",
            "guard_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        })
        assert output["guard_verdict"] == "approve"

    def test_guard_parses_block_verdict(self) -> None:
        mock_llm = _make_mock_llm([
            "## Verdict: BLOCK\n## Feedback: Contains inaccurate claims."
        ])
        pattern = GuardRailPattern(llm=mock_llm)
        output = pattern._guard_check({
            "task": "T",
            "primary_output": "Content",
            "guard_verdict": "",
            "guard_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        })
        assert output["guard_verdict"] == "block"
        assert "inaccurate" in output["guard_feedback"].lower()

    def test_guard_parses_redirect_verdict(self) -> None:
        mock_llm = _make_mock_llm([
            "## Verdict: REDIRECT\n## Feedback: Add more examples."
        ])
        pattern = GuardRailPattern(llm=mock_llm)
        output = pattern._guard_check({
            "task": "T",
            "primary_output": "Content",
            "guard_verdict": "",
            "guard_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        })
        assert output["guard_verdict"] == "redirect"

    def test_guard_defaults_to_approve_on_missing_verdict(self) -> None:
        mock_llm = _make_mock_llm(["No verdict in response."])
        pattern = GuardRailPattern(llm=mock_llm)
        output = pattern._guard_check({
            "task": "T",
            "primary_output": "Content",
            "guard_verdict": "",
            "guard_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        })
        assert output["guard_verdict"] == "approve"


class TestShouldContinue:
    """Verify routing logic."""

    def test_approve_routes_to_approve(self) -> None:
        pattern = GuardRailPattern(llm=_make_mock_llm())
        state: GuardRailState = {
            "task": "T",
            "primary_output": "O",
            "guard_verdict": "approve",
            "guard_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        assert pattern._should_continue(state) == "approve"

    def test_block_routes_to_block(self) -> None:
        pattern = GuardRailPattern(llm=_make_mock_llm())
        state: GuardRailState = {
            "task": "T",
            "primary_output": "O",
            "guard_verdict": "block",
            "guard_feedback": "Fix this",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        assert pattern._should_continue(state) == "block"

    def test_redirect_routes_to_redirect(self) -> None:
        pattern = GuardRailPattern(llm=_make_mock_llm())
        state: GuardRailState = {
            "task": "T",
            "primary_output": "O",
            "guard_verdict": "redirect",
            "guard_feedback": "Improve",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        assert pattern._should_continue(state) == "redirect"

    def test_max_attempts_reached_routes_to_max(self) -> None:
        pattern = GuardRailPattern(llm=_make_mock_llm())
        state: GuardRailState = {
            "task": "T",
            "primary_output": "O",
            "guard_verdict": "block",
            "guard_feedback": "Fix",
            "attempts": 3,
            "max_attempts": 3,
            "final_output": "",
            "safety_violations": [],
        }
        assert pattern._should_continue(state) == "max_attempts"


class TestFullGraphExecution:
    """End-to-end test running the compiled graph with a mock LLM."""

    def test_full_run_approve_first_attempt(self) -> None:
        # Primary generates -> Guard approves -> finalize
        mock_llm = _make_mock_llm([
            "Generated content.",
            "## Verdict: APPROVE\n## Feedback: Good.",
        ])
        pattern = GuardRailPattern(llm=mock_llm)
        result = pattern.run(task="Write about AI")

        assert result["guard_verdict"] == "approve"
        assert result["attempts"] == 1
        assert result["final_output"] == "Generated content."

    def test_full_run_block_then_approve(self) -> None:
        # Attempt 1: block -> Attempt 2: approve
        mock_llm = _make_mock_llm([
            "First content.",
            "## Verdict: BLOCK\n## Feedback: Too vague.",
            "Improved content.",
            "## Verdict: APPROVE\n## Feedback: Good.",
        ])
        pattern = GuardRailPattern(llm=mock_llm)
        result = pattern.run(task="Write about AI")

        assert result["attempts"] == 2
        assert result["guard_verdict"] == "approve"
        assert result["guard_feedback"] == "Good."

    def test_full_run_max_attempts(self) -> None:
        # All attempts blocked, but max reached -> finalize anyway
        mock_llm = _make_mock_llm([
            "Content 1",
            "## Verdict: BLOCK\n## Feedback: Fix.",
            "Content 2",
            "## Verdict: BLOCK\n## Feedback: Fix more.",
            "Content 3",
            "## Verdict: BLOCK\n## Feedback: Still bad.",
        ])
        pattern = GuardRailPattern(llm=mock_llm, max_attempts=3)
        result = pattern.run(task="Write about AI")

        assert result["attempts"] == 3
        # After max attempts, should route to finalize
        assert result["final_output"] == "Content 3"

    def test_llm_call_count_respects_turns(self) -> None:
        mock_llm = _make_mock_llm([
            "C1",
            "## Verdict: BLOCK\n## Feedback: Fix.",
            "C2",
            "## Verdict: APPROVE\n## Feedback: OK.",
        ])
        pattern = GuardRailPattern(llm=mock_llm)
        pattern.run(task="T")
        # 2 primary + 2 guard = 4 calls
        assert mock_llm.invoke.call_count == 4
