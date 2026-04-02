"""Tests for the Swarm pattern."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from patterns.swarm.pattern import SwarmPattern


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
        pattern = SwarmPattern(llm=_make_mock_llm())
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        pattern = SwarmPattern(llm=_make_mock_llm())
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "initialize" in node_names
        assert "agent_turn" in node_names
        assert "aggregator" in node_names


class TestInitialize:
    def test_initialize_sets_task(self) -> None:
        mock_llm = _make_mock_llm(["Opening statement."])
        pattern = SwarmPattern(llm=mock_llm)
        output = pattern._initialize({
            "task": "Analyze this.",
            "agents": [],
            "messages": [],
            "rounds": 0,
            "max_rounds": 3,
            "termination_signal": "",
            "final_conclusion": "",
        })
        assert len(output["messages"]) == 1
        assert output["rounds"] == 1


class TestAgentTurn:
    def test_agent_turn_all_agents_contribute(self) -> None:
        mock_llm = _make_mock_llm([
            "Contribution A.",
            "Contribution B.",
            "Contribution C.",
        ])
        pattern = SwarmPattern(llm=mock_llm)
        output = pattern._agent_turn({
            "task": "Analyze this.",
            "agents": [
                {"name": "Agent A", "specialty": "Strategy"},
                {"name": "Agent B", "specialty": "Tech"},
                {"name": "Agent C", "specialty": "Economics"},
            ],
            "messages": [{"from_agent": "system", "content": "Start."}],
            "rounds": 1,
            "max_rounds": 3,
            "termination_signal": "",
            "final_conclusion": "",
        })
        # All 3 agents called
        assert len(output["messages"]) == 3
        assert output["messages"][0]["from_agent"] == "Agent A"


class TestTermination:
    def test_termination_at_max_rounds(self) -> None:
        """After agent_turn increments rounds to max_rounds, next check ends."""
        # Initialize then agent_turn increments rounds from 1 to 2, check: 2 < 2 = False → end
        mock_llm = _make_mock_llm([
            "Init.",   # initialize
            "A1.",     # agent_turn
            "Final.",  # aggregator
        ])
        pattern = SwarmPattern(llm=mock_llm, max_rounds=2)
        result = pattern.run(
            task="Analyze this.",
            agents=[{"name": "A", "specialty": "X"}],
        )
        assert result["final_conclusion"] != ""


class TestFullGraph:
    def test_full_run_two_agents_two_rounds(self) -> None:
        # max_rounds=3 → 2 agent_turn rounds (rounds become 1 then 2 then 3)
        mock_llm = _make_mock_llm([
            "Init.",   # initialize
            "A1.",     # agent_turn round 1: agent 1
            "A2.",     # agent_turn round 1: agent 2
            "A1r2.",   # agent_turn round 2: agent 1
            "A2r2.",   # agent_turn round 2: agent 2
            "Final.",  # aggregator
        ])
        pattern = SwarmPattern(llm=mock_llm, max_rounds=3)
        result = pattern.run(
            task="Analyze this topic.",
            agents=[
                {"name": "Agent1", "specialty": "Strategy"},
                {"name": "Agent2", "specialty": "Tech"},
            ],
        )
        assert "Final." in result["final_conclusion"]
        assert result["rounds"] == 3  # incremented after each agent_turn
        assert len(result["messages"]) >= 1
