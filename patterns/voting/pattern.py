"""Voting Pattern -- Multiple agents independently decide, then aggregate.

This pattern uses LangGraph's Send API to broadcast the same input to multiple
voter agents in parallel. Each voter produces an independent decision, which
are then aggregated via voting (majority, weighted, or unanimous).

Typical use cases:
  - Architectural decisions requiring diverse expert perspectives
  - Multi-criteria evaluation where different stakeholders have different weights
  - Consensus building across independent agents
  - Risk assessment with multiple independent reviewers
"""

from agentflow.utils import get_default_llm as _default_llm

import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send


# ---------------------------------------------------------------------------
# State schemas
# ---------------------------------------------------------------------------


class VotingState(TypedDict):
    """Top-level graph state for the voting pattern."""

    question: str
    voters: list[dict]  # [{name, expertise, weight}]
    votes: Annotated[list[dict], operator.add]
    aggregated_result: str
    voting_strategy: Literal["majority", "weighted", "unanimous"]


class VoterState(TypedDict):
    """State for an individual voter."""

    voter_name: str
    voter_expertise: str
    question: str


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

VOTER_SYSTEM_PROMPT = (
    "You are an expert consultant with deep knowledge in {expertise}. "
    "You will receive a question requiring a decision or recommendation. "
    "Analyze the question carefully and provide your independent decision "
    "with clear reasoning. Structure your response as:\n\n"
    "## Decision: [Your decision]\n"
    "## Confidence: [High/Medium/Low]\n"
    "## Reasoning: [2-3 paragraphs of analysis]"
)

AGGREGATOR_MAJORITY_PROMPT = (
    "You are a voting aggregator. Multiple experts have cast their votes on a question. "
    "Analyze all votes and determine the majority decision. "
    "If there is a tie, provide a synthesis that acknowledges both positions. "
    "Output a final recommendation based on the majority."
)

AGGREGATOR_WEIGHTED_PROMPT = (
    "You are a weighted voting aggregator. Each expert has a weight based on "
    "their expertise and relevance to the question. Calculate the weighted decision "
    "and provide a final recommendation that accounts for expertise levels. "
    "Higher weight means their decision carries more influence."
)

AGGREGATOR_UNANIMOUS_PROMPT = (
    "You are a unanimous consensus aggregator. All experts must agree for a decision "
    "to be accepted. If there is dissent, identify the key points of disagreement "
    "and provide a revised recommendation that addresses all concerns."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class VotingPattern:
    """LangGraph Voting pattern with parallel voters and aggregation.

    The graph topology is:

        START --> broadcast (Send to all voters)
              +--> voter_1
              +--> voter_2  --+--> aggregator --> END
              +--> voter_N
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        self.llm = llm or _default_llm(model)

    # -- Graph nodes & edges ------------------------------------------------

    def _broadcast(self, state: VotingState) -> list[Send]:
        """Fan-out: emit one Send per voter so each runs in parallel."""
        return [
            Send(
                "voter",
                {
                    "voter_name": voter["name"],
                    "voter_expertise": voter["expertise"],
                    "question": state["question"],
                },
            )
            for voter in state["voters"]
        ]

    def _voter(self, state: VoterState) -> dict:
        """An individual voter processes the question and casts their vote."""
        prompt = VOTER_SYSTEM_PROMPT.format(expertise=state["voter_expertise"])
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Question: {state['question']}"),
        ]
        response = self.llm.invoke(messages)
        return {
            "votes": [
                {
                    "voter": state["voter_name"],
                    "expertise": state["voter_expertise"],
                    "decision": response.content,
                }
            ]
        }

    def _aggregator(self, state: VotingState) -> dict:
        """Aggregate all votes into a final decision."""
        strategy = state.get("voting_strategy", "majority")

        if strategy == "weighted":
            prompt_template = AGGREGATOR_WEIGHTED_PROMPT
        elif strategy == "unanimous":
            prompt_template = AGGREGATOR_UNANIMOUS_PROMPT
        else:
            prompt_template = AGGREGATOR_MAJORITY_PROMPT

        votes_text = "\n\n".join(
            f"### Vote from {v['voter']} (Expertise: {v['expertise']})\n{v['decision']}"
            for v in state["votes"]
        )

        messages = [
            SystemMessage(content=prompt_template),
            HumanMessage(
                content=(
                    f"Question: {state['question']}\n\n"
                    f"Below are {len(state['votes'])} expert votes:\n\n"
                    f"{votes_text}\n\n"
                    f"Strategy: {strategy}. Provide the final aggregated decision."
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return {"aggregated_result": response.content}

    # -- Graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the Voting LangGraph."""
        graph = StateGraph(VotingState)

        graph.add_node("voter", self._voter)
        graph.add_node("aggregator", self._aggregator)

        graph.add_conditional_edges(START, self._broadcast, ["voter"])
        graph.add_edge("voter", "aggregator")
        graph.add_edge("aggregator", END)

        return graph.compile()

    # -- Convenience runner -------------------------------------------------

    def run(
        self,
        question: str,
        voters: list[dict],
        voting_strategy: Literal["majority", "weighted", "unanimous"] = "majority",
    ) -> dict:
        """Build the graph, invoke it, and return the final state dict."""
        compiled = self.build_graph()
        result = compiled.invoke(
            {
                "question": question,
                "voters": voters,
                "votes": [],
                "aggregated_result": "",
                "voting_strategy": voting_strategy,
            }
        )
        return result
