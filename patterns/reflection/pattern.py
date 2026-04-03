"""Reflection Pattern -- Iterative self-improvement through write / review loops.

The Reflection pattern pairs a *writer* agent with a *reviewer* agent.  The
writer produces a first draft, the reviewer critiques it and assigns a numeric
score, and the writer revises -- repeating until the score meets a threshold or
a maximum number of iterations is reached.

This is the simplest -- yet surprisingly effective -- multi-agent pattern.  It
mirrors the human editorial process and reliably improves output quality with
each iteration.
"""

from agentflow.utils import get_default_llm as _default_llm
from agentflow.utils import get_llm_call_count

from langchain_core.callbacks import BaseCallbackHandler

import operator
import re
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ReflectionState(TypedDict):
    """State that flows through the reflection graph."""

    topic: str
    draft: str
    feedback: str
    score: float  # 0-10
    iteration: int
    history: Annotated[list[str], operator.add]


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

WRITER_SYSTEM_PROMPT = (
    "You are an expert long-form writer who produces compelling, well-structured "
    "articles.  Follow these guidelines:\n"
    "\n"
    "1. **Structure** -- Use a clear introduction, logically ordered body sections "
    "with descriptive headings, and a concise conclusion.\n"
    "2. **Depth** -- Provide concrete examples, data points, or analogies that "
    "make abstract ideas tangible.\n"
    "3. **Clarity** -- Write in crisp, jargon-free prose.  Prefer active voice.  "
    "Keep paragraphs focused on a single idea.\n"
    "4. **Engagement** -- Open with a hook that draws the reader in.  End with a "
    "thought-provoking takeaway.\n"
    "5. **Length** -- Aim for 600-1000 words unless instructed otherwise.\n"
    "\n"
    "When revising based on feedback, address every point the reviewer raised "
    "while preserving the strengths they noted.  Do NOT add a preamble like "
    "'Here is the revised article' -- output the article text directly."
)

REVIEWER_SYSTEM_PROMPT = (
    "You are a seasoned editorial reviewer.  Your job is to evaluate an article "
    "draft and provide actionable feedback so the writer can improve it.\n"
    "\n"
    "Evaluate on these dimensions:\n"
    "- **Thesis clarity** -- Is the central argument obvious within the first "
    "two paragraphs?\n"
    "- **Evidence & depth** -- Are claims supported by examples, data, or "
    "reasoning?\n"
    "- **Structure & flow** -- Do sections follow a logical progression?  Are "
    "transitions smooth?\n"
    "- **Language quality** -- Is the prose clear, concise, and free of filler?\n"
    "- **Engagement** -- Does it hold the reader's attention from start to finish?\n"
    "\n"
    "Your response MUST follow this format:\n"
    "1. A short paragraph summarising the draft's main strengths.\n"
    "2. A numbered list of specific, actionable improvements.\n"
    "3. End with exactly one line in the format:  Score: X/10\n"
    "   where X is a number from 1 to 10 (decimals allowed, e.g. 7.5/10).\n"
    "\n"
    "Be constructively critical -- praise what works, be precise about what "
    "does not, and always provide the score line."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------

class ReflectionPattern:
    """Build and run a LangGraph-based reflection loop.

    Parameters
    ----------
    model : str
        OpenAI model name (used when *llm* is not supplied).
    llm : BaseChatModel | None
        Pre-configured LangChain chat model.  Takes precedence over *model*.
    max_iterations : int
        Maximum number of write-review cycles.
    score_threshold : float
        Minimum reviewer score (out of 10) to accept the draft and stop.
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        max_iterations: int = 3,
        score_threshold: float = 8.0,
        counter_handler: BaseCallbackHandler | None = None,
    ):
        self.llm = llm or _default_llm(model, counter_handler)
        self.max_iterations = max_iterations
        self.score_threshold = score_threshold

    # -- graph nodes --------------------------------------------------------

    def _write_node(self, state: ReflectionState) -> dict:
        """Generate or revise the article draft."""

        if state.get("feedback"):
            # Revision pass -- incorporate reviewer feedback.
            user_content = (
                f"Here is your previous draft:\n\n{state['draft']}\n\n"
                f"--- Reviewer feedback ---\n{state['feedback']}\n\n"
                "Please revise the article to address all of the reviewer's "
                "points while keeping the parts that already work well."
            )
        else:
            # First pass -- write from scratch.
            user_content = (
                f"Write a high-quality article on the following topic:\n\n"
                f"{state['topic']}"
            )

        messages = [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        response = self.llm.invoke(messages)
        draft = response.content

        return {
            "draft": draft,
            "history": [draft],
            "iteration": state.get("iteration", 0) + 1,
        }

    def _review_node(self, state: ReflectionState) -> dict:
        """Review the current draft and assign a score."""

        messages = [
            SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Please review the following article draft.\n\n"
                    f"Topic: {state['topic']}\n\n"
                    f"--- Draft ---\n{state['draft']}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        feedback = response.content

        # Parse the numeric score from the reviewer's response.
        match = re.search(r"(\d+(?:\.\d+)?)\s*/?\s*10", feedback)
        score = float(match.group(1)) if match else 5.0

        return {"feedback": feedback, "score": score}

    # -- routing ------------------------------------------------------------

    def _should_continue(self, state: ReflectionState) -> str:
        """Decide whether another write-review cycle is needed."""

        if state["score"] >= self.score_threshold:
            return "end"
        if state["iteration"] >= self.max_iterations:
            return "end"
        return "continue"

    # -- graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the reflection state graph."""

        graph = StateGraph(ReflectionState)

        graph.add_node("write", self._write_node)
        graph.add_node("review", self._review_node)

        graph.add_edge(START, "write")
        graph.add_edge("write", "review")
        graph.add_conditional_edges(
            "review",
            self._should_continue,
            {
                "continue": "write",
                "end": END,
            },
        )

        return graph.compile()

    # -- convenience runner -------------------------------------------------

    def run(self, topic: str) -> dict:
        """Run the full reflection loop and return the final state.

        Parameters
        ----------
        topic : str
            The article topic to write about.

        Returns
        -------
        dict
            Final ``ReflectionState`` containing the polished draft, score,
            iteration count, and revision history.
        """

        graph = self.build_graph()
        initial_state: ReflectionState = {
            "topic": topic,
            "draft": "",
            "feedback": "",
            "score": 0.0,
            "iteration": 0,
            "history": [],
        }
        result = graph.invoke(initial_state)
        result["llm_call_count"] = get_llm_call_count()
        return result
