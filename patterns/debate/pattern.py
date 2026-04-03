"""Debate Pattern — Multi-perspective deliberation with moderator synthesis.

This pattern orchestrates N debaters who argue from different perspectives,
moderated by an LLM that synthesizes arguments and decides when consensus
is reached. Useful for investment decisions, architectural trade-offs,
policy analysis, and any scenario that benefits from adversarial reasoning.

Graph topology:
    START → debate_round → moderator → (continue?) → debate_round or END
"""

from agentflow.utils import (
    LLMCallCounterHandler,
    extract_section,
    get_default_llm as _default_llm,
    get_llm_call_count,
)

import asyncio
import operator


def _run_async(coro):
    """Run coroutine, supporting Jupyter's existing event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
from typing import Annotated, Literal, TypedDict

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class DebateState(TypedDict):
    """Shared state flowing through the debate graph."""

    topic: str
    debaters: list[dict]  # [{name, role, system_prompt}]
    current_round: int
    max_rounds: int
    debate_history: Annotated[list[dict], operator.add]  # [{name, role, argument}]
    moderator_summary: str
    final_decision: str
    is_settled: bool


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

MODERATOR_SYSTEM_PROMPT = (
    "You are a neutral debate moderator. Your responsibilities:\n"
    "1. Summarize each debater's key arguments from the latest round.\n"
    "2. Identify points of agreement and remaining disagreements.\n"
    "3. Decide whether the debate has reached a productive conclusion.\n"
    "4. If the debate IS settled (clear consensus, or arguments have been fully "
    "explored and no new points are emerging), write a final decision that "
    "synthesizes the strongest arguments from all sides.\n"
    "5. If the debate is NOT settled (significant unresolved disagreements, "
    "new angles to explore), summarize the current state and suggest what "
    "debaters should address next.\n\n"
    "Your response MUST follow this exact format:\n"
    "SUMMARY: <your summary of the round>\n"
    "STATUS: SETTLED or CONTINUE\n"
    "DECISION: <final synthesized decision, only if STATUS is SETTLED>\n"
)

DEBATER_TEMPLATE = (
    "You are {name}, arguing from the perspective of: {role}.\n\n"
    "{system_prompt}\n\n"
    "Guidelines for your arguments:\n"
    "- Be specific. Use concrete numbers, examples, and evidence.\n"
    "- Directly respond to points raised by other debaters.\n"
    "- Acknowledge valid points from opponents, but explain why your "
    "position still holds.\n"
    "- Evolve your argument each round — don't repeat yourself.\n"
    "- Keep each argument to 2-3 focused paragraphs."
)


# ---------------------------------------------------------------------------
# Pattern
# ---------------------------------------------------------------------------

class DebatePattern:
    """Orchestrates a multi-round debate between N agents with moderator."""

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        max_rounds: int = 3,
        counter_handler: BaseCallbackHandler | None = None,
    ):
        self.llm = llm or _default_llm(model, counter_handler=counter_handler)
        self.max_rounds = max_rounds

    # ------------------------------------------------------------------
    # Node: debate round
    # ------------------------------------------------------------------

    async def _call_debater(
        self,
        debater: dict,
        topic: str,
        current_round: int,
        history_text: str,
        moderator_summary: str | None,
    ) -> dict:
        """Invoke a single debater's LLM call asynchronously."""
        system_msg = SystemMessage(
            content=DEBATER_TEMPLATE.format(
                name=debater["name"],
                role=debater["role"],
                system_prompt=debater["system_prompt"],
            )
        )

        if current_round == 0 and not history_text:
            user_content = (
                f"The debate topic is:\n\n{topic}\n\n"
                f"Present your opening argument."
            )
        else:
            user_content = (
                f"The debate topic is:\n\n{topic}\n\n"
                f"Previous arguments:\n{history_text}\n\n"
            )
            if moderator_summary:
                user_content += (
                    f"Moderator's latest summary:\n"
                    f"{moderator_summary}\n\n"
                )
            user_content += (
                f"This is round {current_round + 1}. "
                f"Respond to the other debaters and advance your position."
            )

        response = await self.llm.ainvoke(
            [system_msg, HumanMessage(content=user_content)]
        )

        return {
            "name": debater["name"],
            "role": debater["role"],
            "argument": response.content,
            "round": current_round,
        }

    async def _debate_round(self, state: DebateState) -> dict:
        """Each debater produces one argument for the current round (concurrently)."""
        current_round = state["current_round"]
        history_text = self._format_history(state["debate_history"])

        tasks = [
            self._call_debater(
                debater,
                state["topic"],
                current_round,
                history_text,
                state.get("moderator_summary"),
            )
            for debater in state["debaters"]
        ]
        results = await asyncio.gather(*tasks)

        return {
            "debate_history": list(results),
            "current_round": current_round + 1,
        }

    # ------------------------------------------------------------------
    # Node: moderator
    # ------------------------------------------------------------------

    def _moderator(self, state: DebateState) -> dict:
        """Moderator reviews the full debate and decides whether to continue."""
        history_text = self._format_history(state["debate_history"])

        system_msg = SystemMessage(content=MODERATOR_SYSTEM_PROMPT)
        user_content = (
            f"Debate topic: {state['topic']}\n\n"
            f"Full debate transcript:\n{history_text}\n\n"
            f"Current round: {state['current_round']} of {state['max_rounds']}\n\n"
            f"Please provide your moderation."
        )

        response = self.llm.invoke([system_msg, HumanMessage(content=user_content)])
        text = response.content

        # Parse the moderator's structured response
        summary = extract_section(
            text, "SUMMARY", prefix="", known_markers=("SUMMARY:", "STATUS:", "DECISION:")
        )
        status_raw = extract_section(
            text, "STATUS", prefix="", known_markers=("SUMMARY:", "STATUS:", "DECISION:")
        )
        decision = extract_section(
            text, "DECISION", prefix="", known_markers=("SUMMARY:", "STATUS:", "DECISION:")
        )

        # Robust status parsing: check for SETTLED/CONTINUE keyword
        status = status_raw.strip().upper()
        is_settled = "SETTLED" in status

        # If status is empty/malformed but max rounds reached, treat as settled
        if not status_raw.strip() and state["current_round"] >= state["max_rounds"]:
            is_settled = True

        result: dict = {
            "moderator_summary": summary,
            "is_settled": is_settled,
        }

        if is_settled:
            result["final_decision"] = decision if decision else summary

        return result

    # ------------------------------------------------------------------
    # Conditional edge
    # ------------------------------------------------------------------

    def _should_continue(self, state: DebateState) -> Literal["continue", "end"]:
        """Decide whether another debate round is needed."""
        if state.get("is_settled", False):
            return "end"
        if state["current_round"] >= state["max_rounds"]:
            return "end"
        return "continue"

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Build and compile the debate graph."""
        graph = StateGraph(DebateState)

        graph.add_node("debate_round", self._debate_round)
        graph.add_node("moderator", self._moderator)

        graph.add_edge(START, "debate_round")
        graph.add_edge("debate_round", "moderator")

        graph.add_conditional_edges(
            "moderator",
            self._should_continue,
            {
                "continue": "debate_round",
                "end": END,
            },
        )

        return graph.compile()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, topic: str, debaters: list[dict]) -> dict:
        """Run a full debate and return the final state.

        Args:
            topic: The question or proposition to debate.
            debaters: List of dicts with keys ``name``, ``role``,
                      ``system_prompt``.

        Returns:
            Final :class:`DebateState` dict with debate_history,
            moderator_summary, and final_decision.
        """
        graph = self.build_graph()

        initial_state: DebateState = {
            "topic": topic,
            "debaters": debaters,
            "current_round": 0,
            "max_rounds": self.max_rounds,
            "debate_history": [],
            "moderator_summary": "",
            "final_decision": "",
            "is_settled": False,
        }

        result = _run_async(graph.ainvoke(initial_state))
        result["llm_call_count"] = get_llm_call_count(self.counter_handler)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        """Format debate history into readable text."""
        if not history:
            return "(No arguments yet.)"

        lines: list[str] = []
        current_round: int | None = None

        for entry in history:
            entry_round = entry.get("round", 0)
            if entry_round != current_round:
                current_round = entry_round
                lines.append(f"\n--- Round {current_round + 1} ---\n")
            lines.append(f"[{entry['name']} ({entry['role']})]:\n{entry['argument']}\n")

        return "\n".join(lines)

