"""MapReduce Pattern -- Parallel fan-out processing with result aggregation.

This pattern uses LangGraph's Send API to dynamically fan out work to multiple
mapper agents in parallel, then aggregates their results in a single reducer.

Typical use cases:
  - Multi-source research analysis
  - Parallel document summarization
  - Distributed data extraction with synthesis
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

class MapReduceState(TypedDict):
    """Top-level graph state shared across dispatch and reduce phases."""

    topic: str
    sources: list[str]
    results: Annotated[list[dict], operator.add]  # [{source, analysis}]
    final_summary: str


class WorkerState(TypedDict):
    """State for an individual mapper worker."""

    source: str
    topic: str


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

MAPPER_SYSTEM_PROMPT = (
    "You are a research analyst specializing in concise, insightful analysis. "
    "Given a source description and a research topic, provide a focused analysis "
    "of what this source reveals about the topic. Cover key findings, implications, "
    "and notable trends. Keep your analysis to 2-3 paragraphs."
)

REDUCER_SYSTEM_PROMPT = (
    "You are a synthesis expert who combines multiple research analyses into a "
    "coherent, well-structured summary. You identify common themes, contradictions, "
    "and overarching trends across sources. Produce a comprehensive yet concise "
    "synthesis that captures the full picture. Use clear section headers and "
    "highlight the most significant insights."
)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------

class MapReducePattern:
    """LangGraph MapReduce pattern using the Send API for dynamic fan-out.

    The graph topology is:

        START --> dispatch (conditional edges via Send)
              +--> mapper(source_1)
              +--> mapper(source_2)   --+--> reducer --> END
              +--> mapper(source_N)
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
    ) -> None:
        self.llm = llm or _default_llm(model)

    # -- Graph nodes & edges ------------------------------------------------

    def _dispatch(self, state: MapReduceState) -> list[Send]:
        """Fan-out: emit one Send per source so each mapper runs in parallel."""
        return [
            Send("mapper", {"source": source, "topic": state["topic"]})
            for source in state["sources"]
        ]

    def _mapper(self, state: WorkerState) -> dict:
        """Analyse a single source against the research topic."""
        messages = [
            SystemMessage(content=MAPPER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Research topic: {state['topic']}\n\n"
                    f"Source to analyze: {state['source']}\n\n"
                    "Provide your analysis of this source in the context of the "
                    "research topic."
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return {
            "results": [
                {
                    "source": state["source"],
                    "analysis": response.content,
                }
            ]
        }

    def _reducer(self, state: MapReduceState) -> dict:
        """Synthesise all mapper analyses into a single summary."""
        analyses_text = "\n\n---\n\n".join(
            f"Source: {r['source']}\nAnalysis:\n{r['analysis']}"
            for r in state["results"]
        )
        messages = [
            SystemMessage(content=REDUCER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Research topic: {state['topic']}\n\n"
                    f"Below are {len(state['results'])} individual source analyses. "
                    "Synthesize them into a coherent summary.\n\n"
                    f"{analyses_text}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return {"final_summary": response.content}

    # -- Graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the MapReduce LangGraph.

        Uses ``add_conditional_edges`` with :class:`Send` objects so that the
        number of mapper invocations is determined at runtime by the length of
        ``state["sources"]``.
        """
        graph = StateGraph(MapReduceState)

        # Nodes
        graph.add_node("mapper", self._mapper)
        graph.add_node("reducer", self._reducer)

        # Edges
        graph.add_conditional_edges(START, self._dispatch, ["mapper"])
        graph.add_edge("mapper", "reducer")
        graph.add_edge("reducer", END)

        return graph.compile()

    # -- Convenience runner -------------------------------------------------

    def run(self, topic: str, sources: list[str]) -> dict:
        """Build the graph, invoke it, and return the final state dict."""
        compiled = self.build_graph()
        result = compiled.invoke(
            {
                "topic": topic,
                "sources": sources,
                "results": [],
                "final_summary": "",
            }
        )
        return result
