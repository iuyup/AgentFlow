"""Tests for the Chain-of-Experts pattern."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from patterns.chain_of_experts.pattern import ChainOfExpertsPattern


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
        pattern = ChainOfExpertsPattern(llm=_make_mock_llm())
        compiled = pattern.build_graph()
        assert callable(getattr(compiled, "invoke", None))

    def test_build_graph_has_expected_nodes(self) -> None:
        pattern = ChainOfExpertsPattern(llm=_make_mock_llm())
        compiled = pattern.build_graph()
        node_names = set(compiled.get_graph().nodes.keys())
        assert "expert" in node_names
        assert "synthesizer" in node_names


class TestExpertNode:
    def test_expert_produces_output(self) -> None:
        mock_llm = _make_mock_llm(["Expert analysis."])
        pattern = ChainOfExpertsPattern(llm=mock_llm)
        output = pattern._expert_node({
            "task": "Analyze this.",
            "experts": [
                {"name": "Expert1", "specialty": "Analysis", "system_prompt": ""}
            ],
            "current_expert_index": 0,
            "expert_outputs": [],
            "final_synthesis": "",
        })
        assert len(output["expert_outputs"]) == 1
        assert output["expert_outputs"][0]["output"] == "Expert analysis."

    def test_expert_builds_on_previous(self) -> None:
        mock_llm = _make_mock_llm(["Second expert analysis."])
        pattern = ChainOfExpertsPattern(llm=mock_llm)
        output = pattern._expert_node({
            "task": "Analyze this.",
            "experts": [
                {"name": "Expert1", "specialty": "Analysis", "system_prompt": ""},
                {"name": "Expert2", "specialty": "Synthesis", "system_prompt": ""},
            ],
            "current_expert_index": 1,
            "expert_outputs": [
                {"name": "Expert1", "specialty": "Analysis", "output": "First output."}
            ],
            "final_synthesis": "",
        })
        # LLM was called with context containing first expert's output
        assert mock_llm.invoke.call_count == 1


class TestRouting:
    def test_continues_when_more_experts(self) -> None:
        pattern = ChainOfExpertsPattern(llm=_make_mock_llm())
        state = {
            "task": "Analyze this.",
            "experts": [
                {"name": "E1", "specialty": "A", "system_prompt": ""},
                {"name": "E2", "specialty": "B", "system_prompt": ""},
            ],
            "current_expert_index": 0,
            "expert_outputs": [],
            "final_synthesis": "",
        }
        assert pattern._should_continue(state) == "continue"

    def test_synthesizes_after_last_expert(self) -> None:
        pattern = ChainOfExpertsPattern(llm=_make_mock_llm())
        state = {
            "task": "Analyze this.",
            "experts": [
                {"name": "E1", "specialty": "A", "system_prompt": ""},
            ],
            "current_expert_index": 1,  # past last index
            "expert_outputs": [
                {"name": "E1", "specialty": "A", "output": "First output."}
            ],
            "final_synthesis": "",
        }
        assert pattern._should_continue(state) == "synthesize"


class TestSynthesizer:
    def test_synthesizer_produces_final_output(self) -> None:
        mock_llm = _make_mock_llm(["Final synthesis."])
        pattern = ChainOfExpertsPattern(llm=mock_llm)
        output = pattern._synthesizer({
            "task": "Analyze this.",
            "experts": [
                {"name": "E1", "specialty": "A", "system_prompt": ""},
            ],
            "current_expert_index": 1,
            "expert_outputs": [
                {"name": "E1", "specialty": "A", "output": "First output."}
            ],
            "final_synthesis": "",
        })
        assert output["final_synthesis"] == "Final synthesis."


class TestFullGraph:
    def test_full_run_two_experts(self) -> None:
        mock_llm = _make_mock_llm([
            "Expert 1 analysis.",
            "Expert 2 analysis.",
            "Final synthesis.",
        ])
        pattern = ChainOfExpertsPattern(llm=mock_llm)
        result = pattern.run(
            task="Analyze this topic.",
            experts=[
                {"name": "E1", "specialty": "Domain1", "system_prompt": ""},
                {"name": "E2", "specialty": "Domain2", "system_prompt": ""},
            ],
        )
        assert len(result["expert_outputs"]) == 2
        assert "Final synthesis" in result["final_synthesis"]
