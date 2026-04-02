"""Human-in-the-Loop Pattern -- Agent with human approval checkpoints.

This pattern runs a primary agent that executes a task, then pauses at
a review checkpoint for human approval.  The human can approve, reject,
or redirect the task with feedback.
"""

import re
from typing import Annotated, Literal, TypedDict

from agentflow.utils import get_default_llm as _default_llm

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class HumanInTheLoopState(TypedDict):
    """State for the human-in-the-loop pattern."""

    task: str
    primary_output: str
    human_verdict: Literal["", "approve", "reject", "redirect"]
    human_feedback: str
    attempts: int
    max_attempts: int
    final_output: str


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

PRIMARY_SYSTEM_PROMPT = (
    "You are a primary task execution agent. Given a task description, "
    "produce the best possible output. If previous human feedback was provided, "
    "incorporate it carefully to address the concerns raised."
)

REVIEW_SYSTEM_PROMPT = (
    "You are a human review checkpoint. The task output is presented below "
    "for human review. In a real system, a human would evaluate this output "
    "and provide feedback. For this simulation, evaluate the output and "
    "respond with one of the following verdicts:\n\n"
    "## Verdict: [APPROVE / REJECT / REDIRECT]\n"
    "## Feedback: [Your feedback if REJECT or REDIRECT, leave blank if APPROVE]\n\n"
    "Use APPROVE when the output is satisfactory.\n"
    "Use REJECT when the output is fundamentally wrong and must be discarded.\n"
    "Use REDIRECT when the output is mostly good but needs specific improvements."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class HumanInTheLoopPattern:
    """LangGraph Human-in-the-Loop pattern with primary agent and review checkpoint.

    The graph topology is:

        START --> primary_execute --> review
                                      |
                    +--- APPROVE ---->+---> END
                    |                 |
                    +--- REJECT -------+---> primary_execute (retry)
                    |                 |
                    +-- REDIRECT ------+
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        max_attempts: int = 3,
    ):
        self.llm = llm or _default_llm(model)
        self.max_attempts = max_attempts

    def _primary_execute(self, state: HumanInTheLoopState) -> dict:
        """Primary agent generates output."""
        task = state["task"]
        attempts = state.get("attempts", 0)
        feedback = state.get("human_feedback", "")

        if feedback:
            messages = [
                SystemMessage(content=PRIMARY_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Task: {task}\n\n"
                        f"Human feedback (address this):\n{feedback}\n\n"
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

    def _review(self, state: HumanInTheLoopState) -> dict:
        """Review node — simulates human review checkpoint."""
        messages = [
            SystemMessage(content=REVIEW_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Task: {state['task']}\n\n"
                    f"Output to review:\n{state['primary_output']}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        content = response.content

        verdict_match = re.search(
            r"##\s*Verdict:\s*(APPROVE|REJECT|REDIRECT)", content, re.IGNORECASE
        )
        verdict = (
            verdict_match.group(1).upper() if verdict_match else "APPROVE"
        ).lower()

        feedback_match = re.search(
            r"##\s*Feedback:\s*(.*?)(?=\n\n|$)", content, re.DOTALL | re.IGNORECASE
        )
        feedback = feedback_match.group(1).strip() if feedback_match else ""

        return {
            "human_verdict": verdict,
            "human_feedback": feedback,
        }

    def _should_continue(self, state: HumanInTheLoopState) -> str:
        """Route based on human verdict and attempt count."""
        if state["human_verdict"] == "approve":
            return "approve"
        if state["attempts"] >= state.get("max_attempts", self.max_attempts):
            return "max_attempts"
        return state["human_verdict"]

    def _finalize(self, state: HumanInTheLoopState) -> dict:
        """Finalize and set the final output."""
        return {"final_output": state["primary_output"]}

    def build_graph(self) -> StateGraph:
        """Construct and compile the Human-in-the-Loop LangGraph."""
        graph = StateGraph(HumanInTheLoopState)

        graph.add_node("primary_execute", self._primary_execute)
        graph.add_node("review", self._review)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "primary_execute")
        graph.add_edge("primary_execute", "review")

        graph.add_conditional_edges(
            "review",
            self._should_continue,
            {
                "approve": "finalize",
                "reject": "primary_execute",
                "redirect": "primary_execute",
                "max_attempts": "finalize",
            },
        )

        graph.add_edge("finalize", END)

        return graph.compile()

    def run(self, task: str, max_attempts: int | None = None) -> dict:
        """Build the graph, invoke it, and return the final state dict."""
        compiled = self.build_graph()
        max_a = max_attempts or self.max_attempts
        result = compiled.invoke(
            {
                "task": task,
                "primary_output": "",
                "human_verdict": "",
                "human_feedback": "",
                "attempts": 0,
                "max_attempts": max_a,
                "final_output": "",
            }
        )
        return result
