"""Tests for the Debate pattern.

All tests mock ChatOpenAI so they run without an API key.
"""

from unittest.mock import MagicMock, patch

import pytest

from patterns.debate.pattern import (
    DebatePattern,
    DebateState,
    MODERATOR_SYSTEM_PROMPT,
    DEBATER_TEMPLATE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def two_debaters() -> list[dict]:
    return [
        {
            "name": "Bull",
            "role": "Optimistic investor",
            "system_prompt": "You are Bull, an optimistic tech investor.",
        },
        {
            "name": "Bear",
            "role": "Cautious risk analyst",
            "system_prompt": "You are Bear, a cautious risk analyst.",
        },
    ]


@pytest.fixture
def three_debaters() -> list[dict]:
    return [
        {
            "name": "Alice",
            "role": "Proponent",
            "system_prompt": "You are Alice, arguing in favor.",
        },
        {
            "name": "Bob",
            "role": "Opponent",
            "system_prompt": "You are Bob, arguing against.",
        },
        {
            "name": "Carol",
            "role": "Analyst",
            "system_prompt": "You are Carol, providing data-driven analysis.",
        },
    ]


@pytest.fixture
def base_state() -> DebateState:
    return {
        "topic": "Should we adopt microservices?",
        "debaters": [
            {
                "name": "Alice",
                "role": "Proponent",
                "system_prompt": "You are Alice, arguing in favor of microservices.",
            },
            {
                "name": "Bob",
                "role": "Opponent",
                "system_prompt": "You are Bob, arguing against microservices.",
            },
        ],
        "current_round": 0,
        "max_rounds": 3,
        "debate_history": [],
        "moderator_summary": "",
        "final_decision": "",
        "is_settled": False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ai_message(content: str) -> MagicMock:
    """Return a mock AIMessage with the given content."""
    msg = MagicMock()
    msg.content = content
    return msg


# ---------------------------------------------------------------------------
# Tests: graph construction
# ---------------------------------------------------------------------------

def test_build_graph() -> None:
    """Graph builds without error and returns a compiled StateGraph."""
    with patch("patterns.debate.pattern.ChatOpenAI"):
        pattern = DebatePattern()
        graph = pattern.build_graph()
        # Compiled graph has .invoke
        assert callable(graph.invoke)
        # Check nodes are present
        assert "debate_round" in graph.nodes
        assert "moderator" in graph.nodes


def test_build_graph_with_custom_llm(two_debaters: list[dict]) -> None:
    """Passing a custom LLM bypasses ChatOpenAI entirely."""
    custom_llm = MagicMock()
    custom_llm.invoke.return_value = make_ai_message("test")

    pattern = DebatePattern(llm=custom_llm, max_rounds=2)
    graph = pattern.build_graph()

    assert callable(graph.invoke)


# ---------------------------------------------------------------------------
# Tests: debate round
# ---------------------------------------------------------------------------

def test_debate_round_two_debaters(two_debaters: list[dict]) -> None:
    """A single debate round produces one argument per debater."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = make_ai_message(
        "This is my carefully reasoned argument."
    )

    pattern = DebatePattern(llm=mock_llm, max_rounds=3)
    state: DebateState = {
        "topic": "Is AI overhyped?",
        "debaters": two_debaters,
        "current_round": 0,
        "max_rounds": 3,
        "debate_history": [],
        "moderator_summary": "",
        "final_decision": "",
        "is_settled": False,
    }

    result = pattern._debate_round(state)

    # Should have 2 new entries (one per debater)
    assert len(result["debate_history"]) == 2
    assert result["current_round"] == 1

    names = {e["name"] for e in result["debate_history"]}
    assert names == {"Bull", "Bear"}

    # All entries belong to round 0
    assert all(e["round"] == 0 for e in result["debate_history"])


def test_debate_round_three_debaters(three_debaters: list[dict]) -> None:
    """Three debaters each contribute one argument per round."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = make_ai_message("Argument content.")

    pattern = DebatePattern(llm=mock_llm, max_rounds=3)
    state: DebateState = {
        "topic": "Should we migrate to the cloud?",
        "debaters": three_debaters,
        "current_round": 1,
        "max_rounds": 3,
        "debate_history": [
            {"name": "Alice", "role": "Proponent", "argument": "Old argument.", "round": 0},
        ],
        "moderator_summary": "Good start, continue exploring costs.",
        "final_decision": "",
        "is_settled": False,
    }

    result = pattern._debate_round(state)

    assert len(result["debate_history"]) == 3
    assert result["current_round"] == 2

    names = {e["name"] for e in result["debate_history"]}
    assert names == {"Alice", "Bob", "Carol"}


def test_debate_round_llm_receives_system_and_user_messages(
    two_debaters: list[dict]
) -> None:
    """The LLM is invoked with a SystemMessage and a HumanMessage."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = make_ai_message("response")

    pattern = DebatePattern(llm=mock_llm)
    state: DebateState = {
        "topic": "Short topic?",
        "debaters": two_debaters,
        "current_round": 0,
        "max_rounds": 3,
        "debate_history": [],
        "moderator_summary": "",
        "final_decision": "",
        "is_settled": False,
    }

    pattern._debate_round(state)

    # Should be called once per debater
    assert mock_llm.invoke.call_count == 2

    for call_args in mock_llm.invoke.call_args_list:
        messages = call_args[0][0]  # positional args
        # First message should be a SystemMessage
        assert messages[0].__class__.__name__ == "SystemMessage"
        # Second message should be a HumanMessage
        assert messages[1].__class__.__name__ == "HumanMessage"


# ---------------------------------------------------------------------------
# Tests: moderator
# ---------------------------------------------------------------------------

def test_moderator_settles_debate(base_state: DebateState) -> None:
    """Moderator marks debate as settled when consensus is reached."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = make_ai_message(
        "SUMMARY: Both debaters agree that microservices offer scalability "
        "but add complexity.\n"
        "STATUS: SETTLED\n"
        "DECISION: Adopt microservices only for independently deployable "
        "services with clear ownership; keep monolith for tightly coupled domains."
    )

    pattern = DebatePattern(llm=mock_llm, max_rounds=3)
    result = pattern._moderator(base_state)

    assert result["is_settled"] is True
    assert "moderator_summary" in result
    assert "final_decision" in result
    assert "microservices" in result["final_decision"].lower()


def test_moderator_continues_debate(base_state: DebateState) -> None:
    """Moderator asks for another round when disagreements remain."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = make_ai_message(
        "SUMMARY: Alice emphasizes scalability while Bob raises data "
        "consistency risks. They have not yet addressed observability.\n"
        "STATUS: CONTINUE\n"
    )

    pattern = DebatePattern(llm=mock_llm, max_rounds=3)
    result = pattern._moderator(base_state)

    assert result["is_settled"] is False
    assert "moderator_summary" in result
    assert result.get("final_decision", "") == ""


def test_moderator_handles_missing_sections() -> None:
    """Gracefully handles moderator output that omits some sections."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = make_ai_message(
        "SUMMARY: The debate is ongoing.\n"
        "STATUS: CONTINUE\n"
        # No DECISION section
    )

    pattern = DebatePattern(llm=mock_llm)
    state: DebateState = {
        "topic": "Topic?",
        "debaters": [],
        "current_round": 1,
        "max_rounds": 3,
        "debate_history": [],
        "moderator_summary": "",
        "final_decision": "",
        "is_settled": False,
    }

    result = pattern._moderator(state)
    assert result["is_settled"] is False
    assert result["moderator_summary"] != ""


# ---------------------------------------------------------------------------
# Tests: conditional edge
# ---------------------------------------------------------------------------

def test_should_continue_settled(base_state: DebateState) -> None:
    """Returns 'end' when is_settled is True."""
    base_state["is_settled"] = True
    pattern = DebatePattern(llm=MagicMock())
    assert pattern._should_continue(base_state) == "end"


def test_should_continue_max_rounds(base_state: DebateState) -> None:
    """Returns 'end' when max_rounds is reached."""
    base_state["current_round"] = 3
    base_state["max_rounds"] = 3
    base_state["is_settled"] = False
    pattern = DebatePattern(llm=MagicMock())
    assert pattern._should_continue(base_state) == "end"


def test_should_continue_needs_more(base_state: DebateState) -> None:
    """Returns 'continue' when neither settled nor at max rounds."""
    base_state["current_round"] = 1
    base_state["max_rounds"] = 3
    base_state["is_settled"] = False
    pattern = DebatePattern(llm=MagicMock())
    assert pattern._should_continue(base_state) == "continue"


# ---------------------------------------------------------------------------
# Tests: full graph execution
# ---------------------------------------------------------------------------

def test_full_graph_execution_two_debaters_settled(two_debaters: list[dict]) -> None:
    """Full graph runs and reaches settlement after one round."""
    mock_llm = MagicMock()
    call_count = [0]

    def side_effect(messages):
        call_count[0] += 1
        # First 2 calls: debate round (one per debater)
        if call_count[0] <= 2:
            return make_ai_message("Opening argument from debater.")
        # 3rd call: moderator
        return make_ai_message(
            "SUMMARY: Both sides agree on key points.\n"
            "STATUS: SETTLED\n"
            "DECISION: Proceed with the investment with safeguards."
        )

    mock_llm.invoke.side_effect = side_effect

    pattern = DebatePattern(llm=mock_llm, max_rounds=3)
    result = pattern.run(
        topic="Should we invest in AI?",
        debaters=two_debaters,
    )

    assert result["is_settled"] is True
    assert result["final_decision"] != ""
    # 2 debaters + 1 moderator = 3 LLM calls
    assert call_count[0] == 3


def test_full_graph_execution_max_rounds_reached(
    two_debaters: list[dict],
) -> None:
    """Graph runs for max_rounds even if not settled."""

    call_count = [0]

    def side_effect(messages):
        call_count[0] += 1
        # Moderator always says continue until max rounds
        if call_count[0] <= 5:  # 2 debaters * 2 rounds + 1 moderator per round
            return make_ai_message(
                "SUMMARY: Debate continues.\nSTATUS: CONTINUE\n"
            )
        return make_ai_message(
            "SUMMARY: Final round reached.\nSTATUS: CONTINUE\n"
        )

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = side_effect

    pattern = DebatePattern(llm=mock_llm, max_rounds=2)
    result = pattern.run(
        topic="Should we adopt Kubernetes?",
        debaters=two_debaters,
    )

    # Should terminate after max_rounds even without settlement
    assert result["current_round"] == 2
    # 2 rounds * 2 debaters + 2 moderators = 6 calls
    assert call_count[0] == 6


# ---------------------------------------------------------------------------
# Tests: helpers
# ---------------------------------------------------------------------------

def test_format_history_empty() -> None:
    text = DebatePattern._format_history([])
    assert "(No arguments yet.)" in text


def test_format_history_single_entry() -> None:
    history = [
        {"name": "Alice", "role": "Pro", "argument": "Hello world.", "round": 0}
    ]
    text = DebatePattern._format_history(history)
    assert "Alice" in text
    assert "Hello world." in text
    assert "Round 1" in text


def test_format_history_multiple_rounds() -> None:
    history = [
        {"name": "Alice", "role": "Pro", "argument": "Round 1.", "round": 0},
        {"name": "Bob", "role": "Con", "argument": "Round 1.", "round": 0},
        {"name": "Alice", "role": "Pro", "argument": "Round 2.", "round": 1},
        {"name": "Bob", "role": "Con", "argument": "Round 2.", "round": 1},
    ]
    text = DebatePattern._format_history(history)
    assert "Round 1" in text
    assert "Round 2" in text
    assert text.count("--- Round") == 2


def test_extract_section() -> None:
    text = "SUMMARY: A short summary.\nSTATUS: SETTLED\nDECISION: Go ahead."
    assert DebatePattern._extract_section(text, "SUMMARY") == "A short summary."
    assert DebatePattern._extract_section(text, "STATUS") == "SETTLED"
    assert DebatePattern._extract_section(text, "DECISION") == "Go ahead."
    assert DebatePattern._extract_section(text, "MISSING") == ""


# ---------------------------------------------------------------------------
# Tests: prompt constants
# ---------------------------------------------------------------------------

def test_moderator_prompt_exists() -> None:
    assert MODERATOR_SYSTEM_PROMPT is not None
    assert len(MODERATOR_SYSTEM_PROMPT) > 100
    assert "SETTLED" in MODERATOR_SYSTEM_PROMPT
    assert "CONTINUE" in MODERATOR_SYSTEM_PROMPT


def test_debater_template_contains_placeholders() -> None:
    assert "{name}" in DEBATER_TEMPLATE
    assert "{role}" in DEBATER_TEMPLATE
    assert "{system_prompt}" in DEBATER_TEMPLATE
