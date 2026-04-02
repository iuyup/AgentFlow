"""Hierarchical Pattern -- Manager decomposes tasks to Workers, then aggregates.

This pattern uses LangGraph's Send API for dynamic fan-out to multiple
worker agents, which process subtasks in parallel. A manager then
aggregates all worker results into a final output.

Typical use cases:
  - Complex research requiring multiple specialized perspectives
  - Business analysis decomposed into market, technical, and competitive dimensions
  - Multi-faceted content generation with centralized quality control
"""

from agentflow.utils import get_default_llm as _default_llm

import operator
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
# ---------------------------------------------------------------------------
# State schemas
# ---------------------------------------------------------------------------


class HierarchicalState(TypedDict):
    """Top-level graph state for the manager."""

    task: str
    num_workers: int
    decomposed_tasks: Annotated[list[dict], operator.add]
    worker_results: Annotated[list[dict], operator.add]
    final_result: str


class WorkerState(TypedDict):
    """State for an individual worker subgraph."""

    task_id: str
    subtask: str
    reasoning_steps: Annotated[list[str], operator.add]
    result: str


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

MANAGER_DECOMPOSE_PROMPT = (
    "You are a senior project manager specializing in task decomposition. "
    "Given a complex task, break it down into 3-5 independent subtasks that "
    "can be executed in parallel by specialized workers. "
    "For each subtask, provide a clear objective and specific questions to answer. "
    "Output a JSON list of subtasks, each with 'task_id', 'title', and 'objective'."
)

WORKER_SYSTEM_PROMPT = (
    "You are a specialized research analyst. You will receive a subtask with a "
    "clear objective. Analyze the subtask thoroughly and provide a detailed result. "
    "Structure your response with: 'Key Findings', 'Analysis', and 'Recommendations'."
)

MANAGER_AGGREGATE_PROMPT = (
    "You are a senior synthesizer who combines multiple research results into a "
    "coherent, well-structured final report. Review all worker results, identify "
    "cross-cutting themes and insights, and produce a comprehensive synthesis. "
    "Use clear section headers. Highlight the most significant findings."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class HierarchicalPattern:
    """LangGraph Hierarchical pattern with Manager and Worker subgraphs.

    The graph topology is:

        START --> manager_decompose --> dispatch (Send per subtask)
                                          +--> worker_1
                                          +--> worker_2  --+--> manager_aggregate --> END
                                          +--> worker_N
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        self.llm = llm or _default_llm(model)
        self._worker_graph = self._build_worker_graph()

    # -- Worker subgraph (runs independently per subtask) --------------------

    def _build_worker_graph(self):
        """Build the worker subgraph that runs for each subtask."""

        def worker_node(state: WorkerState) -> dict:
            messages = [
                SystemMessage(content=WORKER_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Subtask: {state['subtask']}\n\n"
                        "Provide a thorough analysis following the required structure."
                    )
                ),
            ]
            response = self.llm.invoke(messages)
            return {
                "reasoning_steps": [response.content],
                "result": response.content,
            }

        graph = StateGraph(WorkerState)
        graph.add_node("worker", worker_node)
        graph.add_edge(START, "worker")
        graph.add_edge("worker", END)
        return graph.compile()

    # -- Manager nodes -------------------------------------------------------

    def _manager_decompose(self, state: HierarchicalState) -> dict:
        """Decompose the main task into subtasks for parallel workers."""
        import json

        messages = [
            SystemMessage(content=MANAGER_DECOMPOSE_PROMPT),
            HumanMessage(content=f"Main task: {state['task']}"),
        ]
        response = self.llm.invoke(messages)

        # Parse the LLM response to extract subtasks
        content = response.content.strip()
        subtasks = []

        # Try to find JSON array in response
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            # Try to extract JSON array with regex if raw JSON parsing fails
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list) and len(parsed) > 0:
                    subtasks = parsed

            if not subtasks:
                subtasks = json.loads(content.strip())
        except Exception:
            pass

        # Fallback: parse meaningful lines if JSON parsing failed
        if not subtasks:
            lines = [
                line.strip()
                for line in content.split("\n")
                if line.strip()
                and not line.strip().startswith("#")
                and not line.strip().startswith("```")
                and len(line.strip()) > 10
            ]
            subtasks = [
                {
                    "task_id": f"subtask_{i}",
                    "title": line[:50],
                    "objective": line,
                }
                for i, line in enumerate(lines[:5])
            ]

        # Final safety: if still empty, create a single fallback subtask
        if not subtasks:
            subtasks = [
                {
                    "task_id": "subtask_0",
                    "title": "Main Task",
                    "objective": state["task"],
                }
            ]

        return {"decomposed_tasks": subtasks}

    def _dispatch(self, state: HierarchicalState) -> list[Send]:
        """Fan-out: emit one Send per subtask so each worker runs in parallel."""
        return [
            Send(
                "worker_invoker",
                {
                    "task_id": subtask["task_id"],
                    "subtask": subtask["objective"],
                },
            )
            for subtask in state["decomposed_tasks"]
        ]

    def _worker_invoker(self, state: WorkerState) -> dict:
        """Invoke the worker subgraph for a single subtask."""
        result = self._worker_graph.invoke(state)
        return {
            "worker_results": [
                {
                    "task_id": state["task_id"],
                    "subtask": state["subtask"],
                    "result": result["result"],
                    "reasoning": result["reasoning_steps"],
                }
            ]
        }

    def _manager_aggregate(self, state: HierarchicalState) -> dict:
        """Aggregate all worker results into a final synthesis."""
        # Build context from all worker results
        worker_context = "\n\n".join(
            f"## {r['task_id']}: {r['subtask']}\n\n{r['result']}"
            for r in state["worker_results"]
        )

        messages = [
            SystemMessage(content=MANAGER_AGGREGATE_PROMPT),
            HumanMessage(
                content=(
                    f"Original task: {state['task']}\n\n"
                    f"Below are {len(state['worker_results'])} worker results. "
                    "Synthesize them into a comprehensive final report.\n\n"
                    f"{worker_context}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return {"final_result": response.content}

    # -- Graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the Hierarchical LangGraph."""
        graph = StateGraph(HierarchicalState)

        # Nodes
        graph.add_node("manager_decompose", self._manager_decompose)
        graph.add_node("worker_invoker", self._worker_invoker)
        graph.add_node("manager_aggregate", self._manager_aggregate)

        # Edges
        graph.add_edge(START, "manager_decompose")
        graph.add_conditional_edges(
            "manager_decompose", self._dispatch, ["worker_invoker"]
        )
        graph.add_edge("worker_invoker", "manager_aggregate")
        graph.add_edge("manager_aggregate", END)

        return graph.compile()

    # -- Convenience runner -------------------------------------------------

    def run(self, task: str, num_workers: int | None = None) -> dict:
        """Build the graph, invoke it, and return the final state dict."""
        compiled = self.build_graph()
        result = compiled.invoke(
            {
                "task": task,
                "num_workers": num_workers or 3,
                "decomposed_tasks": [],
                "worker_results": [],
                "final_result": "",
            }
        )
        return result
