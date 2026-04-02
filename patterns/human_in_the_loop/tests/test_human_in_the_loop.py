"""Tests for the Human-in-the-Loop pattern."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from patterns.human_in_the_loop.pattern import HumanInTheLoopPattern


def _make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    mock = MagicMock()
    if responses is None:
        mock.invoke.return_value = AIMessage(content="Mock response.")
    else:
        mock.invoke.side_effect = [
            AIMessage(content=text) for text in responses
        ]
    return mock


class TestBuildGraph:
    def test_build_graph_returns_compiled_graph(self) -> None:
        pattern = HumanInTheLoopPattern(llm=_make_mock_llm())
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        pattern = HumanInTheLoopPattern(llm=_make_mock_llm())
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "primary_execute" in node_names
        assert "review" in node_names
        assert "finalize" in node_names


class TestPrimaryExecute:
    def test_primary_generates_output(self) -> None:
        mock_llm = _make_mock_llm(["Generated output."])
        pattern = HumanInTheLoopPattern(llm=mock_llm)
        output = pattern._primary_execute({
            "task": "Write a summary.",
            "primary_output": "",
            "human_verdict": "",
            "human_feedback": "",
            "attempts": 0,
            "max_attempts": 3,
            "final_output": "",
        })
        assert "Generated output" in output["primary_output"]
        assert output["attempts"] == 1

    def test_primary_incorporates_feedback(self) -> None:
        mock_llm = _make_mock_llm(["Revised output."])
        pattern = HumanInTheLoopPattern(llm=mock_llm)
        output = pattern._primary_execute({
            "task": "Write a summary.",
            "primary_output": "First attempt.",
            "human_verdict": "redirect",
            "human_feedback": "Make it shorter.",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
        })
        assert output["attempts"] == 2


class TestReview:
    def test_review_approve(self) -> None:
        mock_llm = _make_mock_llm([
            "## Verdict: APPROVE\n## Feedback: "
        ])
        pattern = HumanInTheLoopPattern(llm=mock_llm)
        output = pattern._review({
            "task": "Write a summary.",
            "primary_output": "Generated output.",
            "human_verdict": "",
            "human_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
        })
        assert output["human_verdict"] == "approve"

    def test_review_redirect(self) -> None:
        mock_llm = _make_mock_llm([
            "## Verdict: REDIRECT\n## Feedback: Please add more details."
        ])
        pattern = HumanInTheLoopPattern(llm=mock_llm)
        output = pattern._review({
            "task": "Write a summary.",
            "primary_output": "Generated output.",
            "human_verdict": "",
            "human_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
        })
        assert output["human_verdict"] == "redirect"
        assert "more details" in output["human_feedback"]


class TestRouting:
    def test_approve_routes_to_finalize(self) -> None:
        pattern = HumanInTheLoopPattern(llm=_make_mock_llm())
        state = {
            "task": "Write a summary.",
            "primary_output": "Output.",
            "human_verdict": "approve",
            "human_feedback": "",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
        }
        assert pattern._should_continue(state) == "approve"

    def test_reject_routes_back_to_primary(self) -> None:
        pattern = HumanInTheLoopPattern(llm=_make_mock_llm())
        state = {
            "task": "Write a summary.",
            "primary_output": "Wrong output.",
            "human_verdict": "reject",
            "human_feedback": "Incorrect.",
            "attempts": 1,
            "max_attempts": 3,
            "final_output": "",
        }
        assert pattern._should_continue(state) == "reject"

    def test_max_attempts_routes_to_finalize(self) -> None:
        pattern = HumanInTheLoopPattern(llm=_make_mock_llm())
        state = {
            "task": "Write a summary.",
            "primary_output": "Output.",
            "human_verdict": "redirect",
            "human_feedback": "Try again.",
            "attempts": 3,
            "max_attempts": 3,
            "final_output": "",
        }
        assert pattern._should_continue(state) == "max_attempts"


class TestFullGraph:
    def test_full_run_approve_on_first_attempt(self) -> None:
        mock_llm = _make_mock_llm([
            "Primary output.",         # primary_execute
            "## Verdict: APPROVE\n", # review
        ])
        pattern = HumanInTheLoopPattern(llm=mock_llm, max_attempts=3)
        result = pattern.run(task="Write a summary.")

        assert result["final_output"] == "Primary output."
        assert result["human_verdict"] == "approve"
        assert result["attempts"] == 1

    def test_full_run_redirect_and_revise(self) -> None:
        mock_llm = _make_mock_llm([
            "First output.",                 # primary_execute 1
            "## Verdict: REDIRECT\n## Feedback: Improve.",  # review
            "Second output.",                # primary_execute 2
            "## Verdict: APPROVE\n",         # review 2
        ])
        pattern = HumanInTheLoopPattern(llm=mock_llm, max_attempts=3)
        result = pattern.run(task="Write a summary.")

        assert result["attempts"] == 2
        assert result["human_verdict"] == "approve"
        assert result["final_output"] == "Second output."
