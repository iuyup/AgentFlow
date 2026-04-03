"""Chain-of-Experts Pattern -- Sequential expert processing pipeline.

This pattern passes a task through a chain of specialized expert agents,
each adding their perspective before passing to the next expert.
A final synthesizer combines all expert contributions.

Typical use cases:
  - Complex research requiring multiple domain expert reviews
  - Document editing with sequential specialist passes
  - Multi-stage analysis where each expert builds on the previous
"""

import operator
from typing import Annotated, TypedDict

from agentflow.utils import get_default_llm as _default_llm
from agentflow.utils import get_llm_call_count

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class ChainOfExpertsState(TypedDict):
    """State for the chain-of-experts pattern."""

    task: str
    experts: list[dict]  # [{name, specialty, system_prompt}]
    current_expert_index: int
    expert_outputs: Annotated[list[dict], operator.add]  # [{name, output}]
    final_synthesis: str


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

EXPERT_SYSTEM_PROMPT = (
    "You are {name}, a {specialty}. "
    "You will receive a task and the previous expert's output (if any). "
    "Analyze the task, consider the previous expert's input, "
    "and provide your expert contribution. "
    "Focus only on your area of expertise: {specialty}. "
    "Structure your response clearly."
)

SYNTHESIZER_SYSTEM_PROMPT = (
    "You are a final synthesizer. Multiple experts have provided their analysis "
    "on a task. Review all expert contributions and produce a comprehensive "
    "final output that integrates all perspectives. "
    "Highlight key insights, resolve any conflicts between experts, "
    "and provide a coherent conclusion."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class ChainOfExpertsPattern:
    """LangGraph Chain-of-Experts pattern with sequential expert passes.

    The graph topology is:

        START --> expert_1 --> expert_2 --> ... --> expert_N --> synthesizer --> END
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        counter_handler: BaseCallbackHandler | None = None,
    ):
        self.llm = llm or _default_llm(model, counter_handler)

    def _expert_node(self, state: ChainOfExpertsState) -> dict:
        """Each expert processes the task in sequence."""
        idx = state["current_expert_index"]
        expert = state["experts"][idx]
        expert_outputs = state["expert_outputs"]

        # Build context: previous expert outputs
        context = ""
        if expert_outputs:
            context = "\n\n".join(
                f"### {eo['name']}'s contribution:\n{eo['output']}"
                for eo in expert_outputs
            )

        system_msg = SystemMessage(
            content=EXPERT_SYSTEM_PROMPT.format(
                name=expert["name"],
                specialty=expert["specialty"],
                system_prompt=expert.get("system_prompt", ""),
            )
        )

        if context:
            user_content = (
                f"Task: {state['task']}\n\n"
                f"Previous expert contributions:\n{context}\n\n"
                f"Your task as {expert['name']}: Provide your expert analysis."
            )
        else:
            user_content = (
                f"Task: {state['task']}\n\n"
                f"Provide your expert analysis as {expert['name']}."
            )

        response = self.llm.invoke([system_msg, HumanMessage(content=user_content)])

        return {
            "expert_outputs": [
                {
                    "name": expert["name"],
                    "specialty": expert["specialty"],
                    "output": response.content,
                }
            ],
            # Increment here so _should_continue sees updated state
            "current_expert_index": idx + 1,
        }

    def _should_continue(self, state: ChainOfExpertsState) -> str:
        """Continue to next expert or finish."""
        # current_expert_index has already been incremented inside _expert_node
        if state["current_expert_index"] < len(state["experts"]):
            return "continue"
        return "synthesize"

    def _synthesizer(self, state: ChainOfExpertsState) -> dict:
        """Final synthesizer combines all expert outputs."""
        expert_context = "\n\n".join(
            f"## Expert: {eo['name']} ({eo['specialty']})\n{eo['output']}"
            for eo in state["expert_outputs"]
        )

        messages = [
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Original task: {state['task']}\n\n"
                    f"Expert contributions:\n{expert_context}\n\n"
                    "Provide the final synthesis."
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return {"final_synthesis": response.content}

    def _advance_expert(self, state: ChainOfExpertsState) -> dict:
        """Advance to the next expert in the chain."""
        return {"current_expert_index": state["current_expert_index"] + 1}

    def build_graph(self) -> StateGraph:
        """Construct and compile the Chain-of-Experts LangGraph."""
        graph = StateGraph(ChainOfExpertsState)

        graph.add_node("expert", self._expert_node)
        graph.add_node("synthesizer", self._synthesizer)

        graph.add_edge(START, "expert")

        graph.add_conditional_edges(
            "expert",
            self._should_continue,
            {
                "continue": "expert",
                "synthesize": "synthesizer",
            },
        )

        graph.add_edge("synthesizer", END)

        return graph.compile()

    def run(self, task: str, experts: list[dict]) -> dict:
        """Run the chain of experts and return the final state.

        Args:
            task: The task to process.
            experts: List of dicts with keys 'name', 'specialty', 'system_prompt'.
        """
        compiled = self.build_graph()
        result = compiled.invoke(
            {
                "task": task,
                "experts": experts,
                "current_expert_index": 0,
                "expert_outputs": [],
                "final_synthesis": "",
            }
        )
        result["llm_call_count"] = get_llm_call_count(self.counter_handler)
        return result
