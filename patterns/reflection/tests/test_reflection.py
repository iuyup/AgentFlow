"""Tests for the Reflection pattern.

All tests use mocked LLMs — no API key required.
"""

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from patterns.reflection.pattern import ReflectionPattern, ReflectionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(*responses: str) -> MagicMock:
    """Return a mock LLM that yields *responses* in order on successive calls."""
    llm = MagicMock()
    llm.invoke = MagicMock(
        side_effect=[AIMessage(content=r) for r in responses]
    )
    return llm


def _make_pattern(mock_llm: MagicMock, **kwargs) -> ReflectionPattern:
    """Create a ReflectionPattern wired to a mock LLM."""
    return ReflectionPattern(llm=mock_llm, **kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReflectionPattern:
    """Unit and integration tests for ReflectionPattern."""

    # -- graph construction ------------------------------------------------

    def test_build_graph(self):
        """Graph compiles without errors."""
        llm = _make_mock_llm()
        pattern = _make_pattern(llm)
        graph = pattern.build_graph()
        assert graph is not None

    # -- _write_node -------------------------------------------------------

    def test_write_node_initial(self):
        """First write (no prior feedback) generates a draft from the topic."""
        draft_text = "# AI Agents\n\nAI agents are transforming development..."
        llm = _make_mock_llm(draft_text)
        pattern = _make_pattern(llm)

        state: ReflectionState = {
            "topic": "AI Agents",
            "draft": "",
            "feedback": "",
            "score": 0.0,
            "iteration": 0,
            "history": [],
        }

        result = pattern._write_node(state)

        assert result["draft"] == draft_text
        assert result["history"] == [draft_text]
        assert result["iteration"] == 1

    def test_write_node_revision(self):
        """Subsequent write incorporates reviewer feedback."""
        revised_text = "# AI Agents (Revised)\n\nImproved article..."
        llm = _make_mock_llm(revised_text)
        pattern = _make_pattern(llm)

        state: ReflectionState = {
            "topic": "AI Agents",
            "draft": "Original draft text.",
            "feedback": "Add more concrete examples.",
            "score": 5.0,
            "iteration": 1,
            "history": ["Original draft text."],
        }

        result = pattern._write_node(state)

        assert result["draft"] == revised_text
        assert result["history"] == [revised_text]
        assert result["iteration"] == 2

        # Verify the prompt included both the old draft and feedback.
        call_args = llm.invoke.call_args[0][0]
        user_msg = call_args[-1].content
        assert "Original draft text." in user_msg
        assert "Add more concrete examples." in user_msg

    # -- _review_node ------------------------------------------------------

    def test_review_node_score_parsing(self):
        """Score is correctly parsed from standard 'Score: 8/10' format."""
        feedback_text = (
            "Strengths: clear structure.\n"
            "1. Add more data.\n"
            "Score: 8/10"
        )
        llm = _make_mock_llm(feedback_text)
        pattern = _make_pattern(llm)

        state: ReflectionState = {
            "topic": "AI Agents",
            "draft": "Some draft.",
            "feedback": "",
            "score": 0.0,
            "iteration": 1,
            "history": [],
        }

        result = pattern._review_node(state)
        assert result["score"] == 8.0
        assert result["feedback"] == feedback_text

    def test_review_node_score_decimal(self):
        """Decimal scores like '7.5/10' are parsed correctly."""
        feedback_text = "Good work overall.\nScore: 7.5/10"
        llm = _make_mock_llm(feedback_text)
        pattern = _make_pattern(llm)

        state: ReflectionState = {
            "topic": "T",
            "draft": "D",
            "feedback": "",
            "score": 0.0,
            "iteration": 1,
            "history": [],
        }

        result = pattern._review_node(state)
        assert result["score"] == 7.5

    def test_review_node_score_default(self):
        """Unparseable score defaults to 5.0."""
        feedback_text = "Nice article but I forgot to score it."
        llm = _make_mock_llm(feedback_text)
        pattern = _make_pattern(llm)

        state: ReflectionState = {
            "topic": "T",
            "draft": "D",
            "feedback": "",
            "score": 0.0,
            "iteration": 1,
            "history": [],
        }

        result = pattern._review_node(state)
        assert result["score"] == 5.0

    # -- _should_continue --------------------------------------------------

    def test_should_continue_high_score(self):
        """Exits when score meets the threshold."""
        llm = _make_mock_llm()
        pattern = _make_pattern(llm, score_threshold=8.0, max_iterations=5)

        state: ReflectionState = {
            "topic": "T",
            "draft": "D",
            "feedback": "F",
            "score": 8.5,
            "iteration": 1,
            "history": [],
        }
        assert pattern._should_continue(state) == "end"

    def test_should_continue_exact_threshold(self):
        """Exits when score equals the threshold exactly."""
        llm = _make_mock_llm()
        pattern = _make_pattern(llm, score_threshold=8.0, max_iterations=5)

        state: ReflectionState = {
            "topic": "T",
            "draft": "D",
            "feedback": "F",
            "score": 8.0,
            "iteration": 1,
            "history": [],
        }
        assert pattern._should_continue(state) == "end"

    def test_should_continue_max_iterations(self):
        """Exits when max iterations reached, even if score is low."""
        llm = _make_mock_llm()
        pattern = _make_pattern(llm, score_threshold=8.0, max_iterations=3)

        state: ReflectionState = {
            "topic": "T",
            "draft": "D",
            "feedback": "F",
            "score": 5.0,
            "iteration": 3,
            "history": [],
        }
        assert pattern._should_continue(state) == "end"

    def test_should_continue_needs_revision(self):
        """Continues when score is below threshold and iterations remain."""
        llm = _make_mock_llm()
        pattern = _make_pattern(llm, score_threshold=8.0, max_iterations=3)

        state: ReflectionState = {
            "topic": "T",
            "draft": "D",
            "feedback": "F",
            "score": 6.0,
            "iteration": 1,
            "history": [],
        }
        assert pattern._should_continue(state) == "continue"

    # -- full graph execution ----------------------------------------------

    def test_full_graph_high_score_first_round(self):
        """Graph stops after one cycle if the reviewer gives a high score."""
        llm = _make_mock_llm(
            # write pass 1
            "# Great Article\n\nThis is an excellent first draft about AI.",
            # review pass 1 — high score, should stop
            "Excellent writing, clear thesis, strong examples.\n\nScore: 9/10",
        )
        pattern = _make_pattern(llm, max_iterations=3, score_threshold=8.0)

        result = pattern.run("AI Agents")

        assert result["iteration"] == 1
        assert result["score"] == 9.0
        assert "Great Article" in result["draft"]
        assert len(result["history"]) == 1

    def test_full_graph_two_iterations(self):
        """Graph loops twice when the first review score is below threshold."""
        llm = _make_mock_llm(
            # write pass 1
            "Draft version 1 about AI agents.",
            # review pass 1 — low score
            "Needs more depth and examples.\n\nScore: 5/10",
            # write pass 2 (revision)
            "Draft version 2 — improved with examples and depth.",
            # review pass 2 — high score
            "Much improved. Clear, deep, engaging.\n\nScore: 8.5/10",
        )
        pattern = _make_pattern(llm, max_iterations=3, score_threshold=8.0)

        result = pattern.run("AI Agents")

        assert result["iteration"] == 2
        assert result["score"] == 8.5
        assert "version 2" in result["draft"]
        assert len(result["history"]) == 2

    def test_full_graph_max_iterations_reached(self):
        """Graph stops at max_iterations even if score never meets threshold."""
        llm = _make_mock_llm(
            # write 1
            "Draft v1.",
            # review 1
            "Poor. Score: 3/10",
            # write 2
            "Draft v2.",
            # review 2
            "Still not great. Score: 5/10",
        )
        pattern = _make_pattern(llm, max_iterations=2, score_threshold=9.0)

        result = pattern.run("AI Agents")

        assert result["iteration"] == 2
        assert result["score"] == 5.0
        assert len(result["history"]) == 2
