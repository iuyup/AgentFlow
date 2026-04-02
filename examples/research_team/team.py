"""Research Team — Hierarchical + RAG-Agent + GuardRail combination.

Demonstrates composing multiple AgentFlow patterns into a research pipeline.
"""

from typing import Annotated

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from agentflow.utils import get_default_llm as _default_llm


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ResearchTeamState:
    """Top-level state for the research team."""

    question: str
    sub_questions: list[dict]  # [{task_id, question}]
    worker_results: Annotated[list[dict], list.append]
    guardrail_verdict: str
    guardrail_feedback: str
    research_report: str
    safety_violations: list[str]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

MANAGER_PROMPT = (
    "You are a senior research manager. Given a complex research question, "
    "decompose it into 3-4 specific sub-questions that can be answered independently. "
    "Output a JSON list with 'task_id' and 'question' keys."
)

WORKER_PROMPT = (
    "You are a research analyst. Answer your sub-question by reasoning through it. "
    "Be thorough, cite logical steps, and provide a well-reasoned answer."
)

GUARD_PROMPT = (
    "You are a research safety guard. Review the research report for: "
    "(1) Factual accuracy, (2) Logical consistency, (3) No harmful content. "
    "Respond: ## Verdict: [APPROVE / BLOCK] ## Feedback: ..."
)

SYNTHESIZER_PROMPT = (
    "You are the research director. Combine all worker results into a "
    "cohesive research report with sections for each sub-question."
)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class ResearchTeam:
    """Research team combining Hierarchical + RAG-Agent + GuardRail.

    Topology:

        START --> decompose --> [dispatch workers]
                              +--> worker_1
                              +--> worker_2 --> synthesize --> guard --> [APPROVE] --> END
                              +--> worker_3
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
    ):
        self.llm = llm or _default_llm(model)

    def _decompose(self, state: ResearchTeamState) -> dict:
        """Manager decomposes the research question."""
        import json
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=MANAGER_PROMPT),
            HumanMessage(content=f"Research question: {state['question']}"),
        ]
        response = self.llm.invoke(messages)

        content = response.content.strip()
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            sub_questions = json.loads(content.strip())
        except Exception:
            sub_questions = [
                {"task_id": "q1", "question": state["question"]}
            ]

        return {"sub_questions": sub_questions}

    def _dispatch(self, state: ResearchTeamState) -> list:
        """Fan out to one worker per sub-question."""
        from langgraph.types import Send
        return [
            Send("worker", {"task_id": sq["task_id"], "question": sq["question"]})
            for sq in state["sub_questions"]
        ]

    def _worker(self, state: dict) -> dict:
        """Each worker researches its sub-question."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=WORKER_PROMPT),
            HumanMessage(content=f"Sub-question: {state['question']}"),
        ]
        response = self.llm.invoke(messages)

        return {
            "worker_results": [
                {
                    "task_id": state["task_id"],
                    "question": state["question"],
                    "answer": response.content,
                }
            ]
        }

    def _synthesize(self, state: ResearchTeamState) -> dict:
        """Synthesize all worker results into a research report."""
        from langchain_core.messages import HumanMessage, SystemMessage

        results_text = "\n\n".join(
            f"## {r['task_id']}: {r['question']}\n\n{r['answer']}"
            for r in state["worker_results"]
        )

        messages = [
            SystemMessage(content=SYNTHESIZER_PROMPT),
            HumanMessage(
                content=(
                    f"Original question: {state['question']}\n\n"
                    f"Worker results:\n{results_text}\n\n"
                    "Produce the final research report."
                )
            ),
        ]
        response = self.llm.invoke(messages)

        return {"research_report": response.content}

    def _guardrail(self, state: ResearchTeamState) -> dict:
        """Guard checks the research report."""
        import re
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=GUARD_PROMPT),
            HumanMessage(content=state["research_report"]),
        ]
        response = self.llm.invoke(messages)
        content = response.content

        verdict_match = re.search(
            r"##\s*Verdict:\s*(APPROVE|BLOCK)", content, re.IGNORECASE
        )
        verdict = (verdict_match.group(1).upper() if verdict_match else "APPROVE").lower()

        feedback_match = re.search(
            r"##\s*Feedback:\s*(.*?)(?=\n\n|$)", content, re.DOTALL | re.IGNORECASE
        )
        feedback = feedback_match.group(1).strip() if feedback_match else ""

        violations = []
        if verdict == "BLOCK" and any(
            w in content.lower()
            for w in ["harmful", "unsafe", "violation", "dangerous"]
        ):
            violations.append(feedback or "Safety concern detected")

        return {
            "guardrail_verdict": verdict,
            "guardrail_feedback": feedback,
            "safety_violations": violations,
        }

    def _should_retry(self, state: ResearchTeamState) -> str:
        if state.get("guardrail_verdict") == "APPROVE":
            return "approve"
        return "retry"

    def build_graph(self) -> StateGraph:
        """Build the research team graph."""
        from typing import Annotated, TypedDict

        class RTState(TypedDict):
            question: str
            sub_questions: list[dict]
            worker_results: Annotated[list[dict], list.append]
            research_report: str
            guardrail_verdict: str
            guardrail_feedback: str
            safety_violations: Annotated[list[str], list.append]

        graph = StateGraph(RTState)

        graph.add_node("decompose", self._decompose)
        graph.add_node("worker", self._worker)
        graph.add_node("synthesize", self._synthesize)
        graph.add_node("guardrail", self._guardrail)

        graph.add_edge(START, "decompose")

        graph.add_conditional_edges(
            "decompose", self._dispatch, ["worker"]
        )

        graph.add_edge("worker", "synthesize")
        graph.add_edge("synthesize", "guardrail")

        graph.add_conditional_edges(
            "guardrail",
            self._should_retry,
            {
                "approve": END,
                "retry": "decompose",
            },
        )

        return graph.compile()

    def run(self, question: str) -> dict:
        """Run the research team pipeline."""
        compiled = self.build_graph()
        result = compiled.invoke({
            "question": question,
            "sub_questions": [],
            "worker_results": [],
            "research_report": "",
            "guardrail_verdict": "",
            "guardrail_feedback": "",
            "safety_violations": [],
        })
        return result
