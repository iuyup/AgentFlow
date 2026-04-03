"""GuardRail Pattern -- Primary agent with safety guard checkpoint.

This pattern runs a primary agent that executes a task, then routes the output
through a safety/quality guard agent. The guard can approve, block, or redirect.
If blocked or redirected, the primary agent receives specific feedback and retries.

Typical use cases:
  - Content moderation with safety guardrails
  - Code generation with security review
  - Financial transactions with compliance checks
  - Any high-stakes output requiring a second pair of eyes
"""

from agentflow.utils import get_default_llm as _default_llm
from agentflow.utils import get_llm_call_count

from langchain_core.callbacks import BaseCallbackHandler

import operator
import re
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# State schemas
# ---------------------------------------------------------------------------


class GuardRailState(TypedDict):
    """Top-level graph state for the guardrail pattern."""

    task: str
    primary_output: str
    guard_verdict: Literal["approve", "block", "redirect"]
    guard_feedback: str
    attempts: int
    max_attempts: int
    final_output: str
    safety_violations: Annotated[list[str], operator.add]


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

PRIMARY_SYSTEM_PROMPT = (
    "You are a primary content generation agent. You produce high-quality output "
    "based on the task description. If previous feedback was provided, incorporate "
    "it carefully to address the concerns raised."
)

GUARD_SYSTEM_PROMPT = (
    "You are a safety and quality guard agent. Your job is to review the output "
    "from a primary agent and determine if it is safe, appropriate, and meets "
    "quality standards.\n\n"
    "Evaluate the output on:\n"
    "1. Safety: No harmful, unethical, or dangerous content\n"
    "2. Accuracy: Factually correct and not misleading\n"
    "3. Quality: Well-written and fit for purpose\n\n"
    "Respond with a structured verdict:\n\n"
    "## Verdict: [APPROVE / BLOCK / REDIRECT]\n"
    "## Feedback: [If BLOCK or REDIRECT, provide specific, actionable feedback]\n\n"
    "Use BLOCK when the output contains serious violations that must be fixed.\n"
    "Use REDIRECT when the output is mostly good but needs minor improvements.\n"
    "Use APPROVE when the output is satisfactory."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class GuardRailPattern:
    """LangGraph GuardRail pattern with primary + guard checkpoint.

    The graph topology is:

        START --> primary_execute --> guard_check
                                      |
                    +--- APPROVE ---->+---> END
                    |                 |
                    +--- BLOCK -------+---> primary_execute (retry)
                    |                 |
                    +-- REDIRECT ------+
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        max_attempts: int = 3,
        counter_handler: BaseCallbackHandler | None = None,
    ) -> None:
        self.llm = llm or _default_llm(model, counter_handler)
        self.max_attempts = max_attempts

    # -- Graph nodes -------------------------------------------------------

    def _primary_execute(self, state: GuardRailState) -> dict:
        """Primary agent generates output."""
        task = state["task"]
        attempts = state.get("attempts", 0)
        feedback = state.get("guard_feedback", "")

        if feedback:
            messages = [
                SystemMessage(content=PRIMARY_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Task: {task}\n\n"
                        f"Previous feedback (address this in your revision):\n{feedback}\n\n"
                        "Provide an improved output."
                    )
                ),
            ]
        else:
            messages = [
                SystemMessage(content=PRIMARY_SYSTEM_PROMPT),
                HumanMessage(content=f"Task: {task}"),
            ]

        response = self.llm.invoke(messages)
        return {
            "primary_output": response.content,
            "attempts": attempts + 1,
        }

    def _guard_check(self, state: GuardRailState) -> dict:
        """Guard agent reviews the primary output."""
        messages = [
            SystemMessage(content=GUARD_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Task: {state['task']}\n\n"
                    f"Primary output to review:\n{state['primary_output']}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        content = response.content

        # Parse verdict
        verdict_match = re.search(
            r"##\s*Verdict:\s*(APPROVE|BLOCK|REDIRECT)", content, re.IGNORECASE
        )
        verdict = (verdict_match.group(1).upper() if verdict_match else "APPROVE").lower()

        # Parse feedback
        feedback_match = re.search(r"##\s*Feedback:\s*(.*?)(?=\n\n|$)", content, re.DOTALL | re.IGNORECASE)
        feedback = feedback_match.group(1).strip() if feedback_match else ""

        # Track safety violations
        safety_violations = []
        if verdict == "block" and any(
            word in content.lower()
            for word in ["harmful", "unsafe", "violation", "dangerous", "inappropriate"]
        ):
            safety_violations.append(feedback or "Safety violation detected")

        return {
            "guard_verdict": verdict,
            "guard_feedback": feedback,
            "safety_violations": safety_violations,
        }

    def _should_continue(self, state: GuardRailState) -> str:
        """Route based on guard verdict and attempt count."""
        if state["guard_verdict"] == "approve":
            return "approve"
        if state["attempts"] >= state.get("max_attempts", self.max_attempts):
            # Max attempts reached, accept current output
            return "max_attempts"
        return state["guard_verdict"]

    def _finalize(self, state: GuardRailState) -> dict:
        """Finalize and set the final output."""
        return {"final_output": state["primary_output"]}

    # -- Graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the GuardRail LangGraph."""
        graph = StateGraph(GuardRailState)

        graph.add_node("primary_execute", self._primary_execute)
        graph.add_node("guard_check", self._guard_check)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "primary_execute")
        graph.add_edge("primary_execute", "guard_check")

        graph.add_conditional_edges(
            "guard_check",
            self._should_continue,
            {
                "approve": "finalize",
                "block": "primary_execute",
                "redirect": "primary_execute",
                "max_attempts": "finalize",
            },
        )

        graph.add_edge("finalize", END)

        return graph.compile()

    # -- Convenience runner -------------------------------------------------

    def run(self, task: str, max_attempts: int | None = None) -> dict:
        """Build the graph, invoke it, and return the final state dict."""
        compiled = self.build_graph()
        max_a = max_attempts or self.max_attempts
        result = compiled.invoke(
            {
                "task": task,
                "primary_output": "",
                "guard_verdict": "",
                "guard_feedback": "",
                "attempts": 0,
                "max_attempts": max_a,
                "final_output": "",
                "safety_violations": [],
            }
        )
        result["llm_call_count"] = get_llm_call_count()
        return result
