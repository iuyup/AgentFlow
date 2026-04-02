"""Tests for the Voting pattern.

All tests mock the LLM so they run without an API key and are fully
deterministic.
"""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langgraph.types import Send

from patterns.voting.pattern import (
    VoterState,
    VotingPattern,
    VotingState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(responses: list[str] | None = None) -> MagicMock:
    """Return a mock LLM whose ``.invoke()`` yields *responses* in order."""
    mock = MagicMock()
    if responses is None:
        mock.invoke.return_value = AIMessage(content="Mock vote.")
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
        pattern = VotingPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = VotingPattern(llm=mock_llm)
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "voter" in node_names
        assert "aggregator" in node_names


class TestBroadcastFanOut:
    """Verify that _broadcast produces the correct Send objects."""

    def test_broadcast_returns_one_send_per_voter(self) -> None:
        mock_llm = _make_mock_llm()
        pattern = VotingPattern(llm=mock_llm)
        voters = [
            {"name": "Alice", "expertise": "Security"},
            {"name": "Bob", "expertise": "Performance"},
        ]
        state: VotingState = {
            "question": "Which cloud provider?",
            "voters": voters,
            "votes": [],
            "aggregated_result": "",
            "voting_strategy": "majority",
        }
        sends = pattern._broadcast(state)
        assert len(sends) == 2

    def test_broadcast_send_targets_voter_node(self) -> None:
        pattern = VotingPattern(llm=_make_mock_llm())
        sends = pattern._broadcast({
            "question": "Q",
            "voters": [{"name": "A", "expertise": "E"}],
            "votes": [],
            "aggregated_result": "",
            "voting_strategy": "majority",
        })
        assert all(isinstance(s, Send) for s in sends)
        assert sends[0].node == "voter"

    def test_broadcast_send_contains_voter_info_and_question(self) -> None:
        pattern = VotingPattern(llm=_make_mock_llm())
        sends = pattern._broadcast({
            "question": "Choose Python or Go?",
            "voters": [{"name": "Alice", "expertise": "Systems"}],
            "votes": [],
            "aggregated_result": "",
            "voting_strategy": "weighted",
        })
        payload = sends[0].arg
        assert payload["voter_name"] == "Alice"
        assert payload["voter_expertise"] == "Systems"
        assert payload["question"] == "Choose Python or Go?"

    def test_broadcast_empty_voters(self) -> None:
        pattern = VotingPattern(llm=_make_mock_llm())
        sends = pattern._broadcast({
            "question": "Q",
            "voters": [],
            "votes": [],
            "aggregated_result": "",
            "voting_strategy": "majority",
        })
        assert sends == []


class TestVoterNode:
    """Verify voter node processes question and returns vote."""

    def test_voter_returns_vote_dict(self) -> None:
        mock_llm = _make_mock_llm(["My decision: Choose Python for its ecosystem."])
        pattern = VotingPattern(llm=mock_llm)
        state: VoterState = {
            "voter_name": "Alice",
            "voter_expertise": "Systems Programming",
            "question": "Python or Go?",
        }
        output = pattern._voter(state)
        assert "votes" in output
        assert len(output["votes"]) == 1

    def test_voter_vote_contains_name_expertise_and_decision(self) -> None:
        decision = "Go is better for concurrency."
        mock_llm = _make_mock_llm([decision])
        pattern = VotingPattern(llm=mock_llm)
        output = pattern._voter({
            "voter_name": "Bob",
            "voter_expertise": "Backend",
            "question": "Backend stack?",
        })
        vote = output["votes"][0]
        assert vote["voter"] == "Bob"
        assert vote["expertise"] == "Backend"
        assert vote["decision"] == decision

    def test_voter_includes_expertise_in_system_prompt(self) -> None:
        mock_llm = _make_mock_llm(["ok"])
        pattern = VotingPattern(llm=mock_llm)
        pattern._voter({
            "voter_name": "C",
            "voter_expertise": "Security Engineering",
            "question": "Auth strategy?",
        })
        messages = mock_llm.invoke.call_args[0][0]
        assert "Security Engineering" in messages[0].content


class TestAggregatorNode:
    """Verify aggregator combines votes based on strategy."""

    def test_aggregator_returns_aggregated_result(self) -> None:
        synthesis = "Majority voted for Python."
        mock_llm = _make_mock_llm([synthesis])
        pattern = VotingPattern(llm=mock_llm)
        state: VotingState = {
            "question": "Python or Go?",
            "voters": [],
            "votes": [
                {"voter": "A", "expertise": "E", "decision": "Python"},
                {"voter": "B", "expertise": "E", "decision": "Python"},
            ],
            "aggregated_result": "",
            "voting_strategy": "majority",
        }
        output = pattern._aggregator(state)
        assert output["aggregated_result"] == synthesis

    def test_aggregator_includes_all_votes_in_prompt(self) -> None:
        mock_llm = _make_mock_llm(["final"])
        pattern = VotingPattern(llm=mock_llm)
        state: VotingState = {
            "question": "Q",
            "voters": [],
            "votes": [
                {"voter": "Alice", "expertise": "Sec", "decision": "Vote A"},
                {"voter": "Bob", "expertise": "Perf", "decision": "Vote B"},
            ],
            "aggregated_result": "",
            "voting_strategy": "majority",
        }
        pattern._aggregator(state)
        messages = mock_llm.invoke.call_args[0][0]
        human_content = messages[1].content
        assert "Alice" in human_content
        assert "Vote A" in human_content
        assert "Bob" in human_content
        assert "Vote B" in human_content

    def test_aggregator_uses_weighted_prompt_when_strategy_weighted(self) -> None:
        mock_llm = _make_mock_llm(["weighted result"])
        pattern = VotingPattern(llm=mock_llm)
        state: VotingState = {
            "question": "Q",
            "voters": [],
            "votes": [{"voter": "A", "expertise": "E", "decision": "D"}],
            "aggregated_result": "",
            "voting_strategy": "weighted",
        }
        pattern._aggregator(state)
        messages = mock_llm.invoke.call_args[0][0]
        assert "weighted" in messages[0].content.lower()


class TestFullGraphExecution:
    """End-to-end test running the compiled graph with a mock LLM."""

    def test_full_run_with_three_voters(self) -> None:
        responses = [
            "Alice vote: Python",
            "Bob vote: Go",
            "Carol vote: Python",
            "Majority synthesis: Python wins",
        ]
        mock_llm = _make_mock_llm(responses)
        pattern = VotingPattern(llm=mock_llm)

        voters = [
            {"name": "Alice", "expertise": "Systems"},
            {"name": "Bob", "expertise": "Performance"},
            {"name": "Carol", "expertise": "Web"},
        ]
        result = pattern.run(
            question="Best backend language?",
            voters=voters,
            voting_strategy="majority",
        )

        assert result["question"] == "Best backend language?"
        assert len(result["votes"]) == 3
        assert result["aggregated_result"] == "Majority synthesis: Python wins"

    def test_full_run_weighted_strategy(self) -> None:
        # 2 voters + 1 aggregator = 3 LLM calls
        mock_llm = _make_mock_llm(["a", "b", "weighted synthesis"])
        pattern = VotingPattern(llm=mock_llm)

        result = pattern.run(
            question="Cloud provider?",
            voters=[
                {"name": "A", "expertise": "X"},
                {"name": "B", "expertise": "Y"},
            ],
            voting_strategy="weighted",
        )

        assert len(result["votes"]) == 2
        assert result["voting_strategy"] == "weighted"
        assert result["aggregated_result"] == "weighted synthesis"

    def test_llm_called_correct_number_of_times(self) -> None:
        voters = [{"name": f"V{i}", "expertise": "E"} for i in range(3)]
        mock_llm = _make_mock_llm(["v1", "v2", "v3", "synthesis"])
        pattern = VotingPattern(llm=mock_llm)
        pattern.run(question="Q", voters=voters, voting_strategy="majority")
        # 3 voter calls + 1 aggregator call = 4
        assert mock_llm.invoke.call_count == 4
