"""Swarm Pattern -- Decentralized multi-agent collective intelligence.

This pattern uses a population of specialized agents that collaborate
through message passing without a central coordinator.  Agents share
information, build on each other's work, and collectively reach conclusions.
"""

import operator
from typing import Annotated, Literal, TypedDict

from agentflow.utils import get_default_llm as _default_llm

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class SwarmState(TypedDict):
    """State for the swarm pattern."""

    task: str
    agents: list[dict]  # [{name, specialty}]
    messages: Annotated[list[dict], operator.add]  # [{from_agent, content}]
    rounds: int
    max_rounds: int
    termination_signal: str  # "" = continue, "converged" / "max_rounds" = end
    final_conclusion: str


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

SWARM_AGENT_PROMPT = (
    "You are {name}, a {specialty} expert. "
    "You are part of a decentralized collective of agents working on a task. "
    "You have access to all messages exchanged so far. "
    "Review the existing discussion, build on the best ideas, "
    "and add your expert perspective. "
    "Keep your contribution focused and additive — don't repeat what's already been said."
)

AGGREGATOR_PROMPT = (
    "You are a collective intelligence aggregator. Multiple agents have "
    "contributed their perspectives on the task. Analyze all contributions, "
    "identify the key themes and strongest insights, and produce a final "
    "conclusion that reflects the collective intelligence of the group."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class SwarmPattern:
    """LangGraph Swarm pattern — decentralized multi-agent collective.

    The graph topology is:

        START --> initialize --> [broadcast to all agents]
                                   agent_a <--> agent_b <--> agent_c
                                   [termination check]
                                   --> aggregator --> END
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        max_rounds: int = 3,
    ):
        self.llm = llm or _default_llm(model)
        self.max_rounds = max_rounds

    def _initialize(self, state: SwarmState) -> dict:
        """Initialize the swarm with an opening statement."""
        messages = [
            SystemMessage(
                content=(
                    "You are initiating a decentralized collective intelligence session.\n"
                    f"Task: {state['task']}\n\n"
                    "Each agent will contribute their expertise. "
                    "Review all contributions carefully and add your unique perspective."
                )
            ),
            HumanMessage(content=state["task"]),
        ]
        response = self.llm.invoke(messages)
        return {
            "messages": [
                {
                    "from_agent": "system",
                    "content": f"Task initiated: {state['task']}\n\n{response.content}",
                }
            ],
            "rounds": 1,
        }

    def _agent_turn(self, state: SwarmState) -> dict:
        """Each agent contributes to the collective discussion."""
        # Build context from all previous messages
        context = "\n\n".join(
            f"[{m['from_agent']}]: {m['content'][:500]}"
            for m in state["messages"]
        )

        new_messages = []
        for agent in state["agents"]:
            system_msg = SystemMessage(
                content=SWARM_AGENT_PROMPT.format(
                    name=agent["name"],
                    specialty=agent["specialty"],
                )
            )
            user_content = (
                f"Collective task: {state['task']}\n\n"
                f"Discussion so far:\n{context}\n\n"
                f"Your contribution as {agent['name']}:"
            )
            response = self.llm.invoke([system_msg, HumanMessage(content=user_content)])
            new_messages.append({
                "from_agent": agent["name"],
                "content": response.content,
            })

        return {
            "messages": new_messages,
            # Increment here so conditional edge sees updated state
            "rounds": state["rounds"] + 1,
        }

    def _check_termination(self, state: SwarmState) -> str:
        """Check if the swarm should terminate.

        Called with state AFTER _agent_turn has incremented rounds.
        rounds=1 after first agent_turn, so:
        - if max_rounds=2: 1 < 2 → continue; 2 < 2 → end
        - if max_rounds=3: 1 < 3 → continue; 2 < 3 → continue; 3 < 3 → end
        """
        if state["rounds"] < state.get("max_rounds", self.max_rounds):
            return "continue"
        return "end"

    def _aggregator(self, state: SwarmState) -> dict:
        """Final aggregator synthesizes all agent contributions."""
        discussion = "\n\n".join(
            f"### {m['from_agent']}:\n{m['content']}"
            for m in state["messages"]
        )

        messages = [
            SystemMessage(content=AGGREGATOR_PROMPT),
            HumanMessage(
                content=(
                    f"Original task: {state['task']}\n\n"
                    f"Collective discussion:\n{discussion}\n\n"
                    "Provide the final collective conclusion."
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return {"final_conclusion": response.content}

    def build_graph(self) -> StateGraph:
        """Construct and compile the Swarm LangGraph."""
        graph = StateGraph(SwarmState)

        graph.add_node("initialize", self._initialize)
        graph.add_node("agent_turn", self._agent_turn)
        graph.add_node("aggregator", self._aggregator)

        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "agent_turn")

        # Agent turn loops back until termination.
        # rounds is incremented INSIDE _agent_turn, so the lambda sees the
        # post-increment value: continue if rounds < max_rounds.
        graph.add_conditional_edges(
            "agent_turn",
            self._check_termination,
            {
                "continue": "agent_turn",
                "end": "aggregator",
            },
        )

        graph.add_edge("aggregator", END)

        return graph.compile()

    def run(self, task: str, agents: list[dict]) -> dict:
        """Run the swarm and return the final state.

        Args:
            task: The task for the collective to solve.
            agents: List of dicts with keys 'name' and 'specialty'.
        """
        compiled = self.build_graph()
        result = compiled.invoke(
            {
                "task": task,
                "agents": agents,
                "messages": [],
                "rounds": 0,
                "max_rounds": self.max_rounds,
                "termination_signal": "",
                "final_conclusion": "",
            }
        )
        return result
