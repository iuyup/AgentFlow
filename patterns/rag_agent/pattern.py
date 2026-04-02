"""RAG-Agent Pattern -- Agent with on-demand retrieval augmentation.

This pattern implements a retrieval-augmented agent that decides when to
retrieve additional context based on the task. The agent can call a retrieval
tool, synthesize the results, and continue reasoning until satisfied.

Typical use cases:
  - Question answering over a knowledge base
  - Codebase-aware AI assistant
  - Document Q&A with selective retrieval
  - Real-time information lookup during reasoning
"""

import operator
import re
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph


def _default_llm(model: str | None = None):
    """Auto-detect provider and select appropriate default model."""
    import os

    if os.getenv("DEEPSEEK_API_KEY"):
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(model=model or "deepseek-chat")
    return ChatOpenAI(model=model or "gpt-4o-mini")


# ---------------------------------------------------------------------------
# State schemas
# ---------------------------------------------------------------------------


class RAGAgentState(TypedDict):
    """State for the RAG agent."""

    query: str
    retrieved_docs: Annotated[list[dict], operator.add]
    agent_reasoning: Annotated[list[str], operator.add]
    response: str
    retrieval_count: int
    max_retrievals: int
    decision: Literal["", "retrieve", "answer"]


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

RAG_AGENT_SYSTEM_PROMPT = (
    "You are a knowledgeable assistant with access to a document retrieval system. "
    "Given a user query, decide whether you need to retrieve additional documents "
    "to provide an accurate, comprehensive answer.\n\n"
    "Output your response in this format:\n\n"
    "## Decision: [RETRIEVE / ANSWER]\n"
    "## Reasoning: [Your reasoning]\n"
    "## Documents (if RETRIEVE): [List document IDs or search queries, one per line]\n"
    "## Answer (if ANSWER): [Your final answer to the query]\n\n"
    "Guidelines:\n"
    "- Retrieve if the query requires specific facts, details, or information you don't have\n"
    "- Retrieve if the query mentions specific documents, files, or data sources\n"
    "- Answer directly if the query is a general question you can answer confidently\n"
    "- Never fabricate information; retrieve if unsure"
)

SYNTHESIZE_PROMPT = (
    "You have retrieved the following documents. Read them carefully and "
    "synthesize the relevant information to answer the user's query.\n\n"
    "Query: {query}\n\n"
    "Documents:\n{docs}\n\n"
    "Provide a comprehensive answer based on the retrieved documents."
)


# ---------------------------------------------------------------------------
# Mock retrieval function (simulates document retrieval)
# ---------------------------------------------------------------------------

_MOCK_DOCUMENTS = {
    "doc1": "Python is a high-level programming language known for its readability. "
    "Created by Guido van Rossum in 1991, it supports multiple programming paradigms.",
    "doc2": "LangGraph is a library for building stateful applications with LLMs "
    "using directed graphs. It extends LangChain with graph-based workflows.",
    "doc3": "Retrieval-Augmented Generation (RAG) combines the power of LLMs "
    "with external knowledge bases. It retrieves relevant documents to ground LLM responses.",
    "doc4": "Vector databases store embeddings and enable semantic search. "
    "Popular options include Pinecone, Weaviate, and Chroma.",
    "doc5": "Agentic AI refers to AI systems that can autonomously plan and execute "
    "multi-step tasks. They use tools and can adapt based on feedback.",
}


def _retrieve_docs(doc_ids: list[str]) -> list[dict]:
    """Simulate document retrieval. Returns list of doc dicts."""
    docs = []
    for doc_id in doc_ids:
        if doc_id in _MOCK_DOCUMENTS:
            docs.append({
                "doc_id": doc_id,
                "content": _MOCK_DOCUMENTS[doc_id],
            })
        else:
            docs.append({
                "doc_id": doc_id,
                "content": f"Document {doc_id} not found.",
            })
    return docs


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class RAGAgentPattern:
    """LangGraph RAG-Agent pattern with conditional retrieval.

    The graph topology is:

        START --> agent --> [retrieve] --> fetch --> synthesize --> agent
                   |          |                                     |
                   +--- [answer] --------------------------------> END
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        max_retrievals: int = 3,
    ) -> None:
        self.llm = llm or _default_llm(model)
        self.max_retrievals = max_retrievals
        # Shared context: docs requested by agent, used by fetch node
        self._pending_docs: list[str] = []

    # -- Graph nodes -------------------------------------------------------

    def _agent(self, state: RAGAgentState) -> dict:
        """Agent decides whether to retrieve or answer."""
        query = state["query"]
        docs_so_far = state["retrieved_docs"]
        retrieval_count = state.get("retrieval_count", 0)

        context = ""
        if docs_so_far:
            context = "\n\nPreviously retrieved documents:\n" + "\n".join(
                f"- [{d['doc_id']}] {d['content'][:200]}..." for d in docs_so_far
            )

        messages = [
            SystemMessage(content=RAG_AGENT_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Query: {query}\n\n"
                    f"Retrieval count: {retrieval_count}/{state['max_retrievals']}"
                    f"{context}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        content = response.content

        # Parse decision
        decision_match = re.search(
            r"##\s*Decision:\s*(RETRIEVE|ANSWER)", content, re.IGNORECASE
        )
        decision = (decision_match.group(1).upper() if decision_match else "ANSWER")

        # Parse document IDs if RETRIEVE
        doc_ids = []
        if decision == "RETRIEVE":
            # Handle both "## Documents: doc1 doc2" and "## Docs:\ndoc1\ndoc2"
            docs_section = re.search(
                r"##\s*Docs?[^:]*:\s*\n?(.*?)(?=##|\Z)", content, re.DOTALL | re.IGNORECASE
            )
            if docs_section:
                raw = docs_section.group(1).strip()
                doc_ids = [
                    line.strip()
                    for line in raw.split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ][:5]

        # Parse answer if ANSWER
        answer = ""
        if decision == "ANSWER":
            answer_match = re.search(
                r"##\s*Answer:\s*(.*?)(?=##|\Z)", content, re.DOTALL | re.IGNORECASE
            )
            answer = answer_match.group(1).strip() if answer_match else content

        # Parse reasoning
        reasoning_match = re.search(
            r"##\s*Reasoning:\s*(.*?)(?=##|\Z)", content, re.DOTALL | re.IGNORECASE
        )
        reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

        # Store pending docs in instance for fetch node to access
        self._pending_docs = doc_ids

        return {
            "decision": decision.lower(),
            "docs_to_retrieve": doc_ids,
            "response": answer,
            "agent_reasoning": [reasoning],
        }

    def _route(self, state: RAGAgentState) -> str:
        """Route based on agent's decision and retrieval count."""
        decision = state.get("decision", "")
        count = state.get("retrieval_count", 0)
        max_r = state.get("max_retrievals", self.max_retrievals)

        if decision == "answer":
            return "answer"
        if decision == "retrieve":
            if count >= max_r:
                return "max_retrievals"
            return "retrieve"
        # Default: answer
        return "answer"

    def _fetch(self, state: RAGAgentState) -> dict:
        """Fetch documents based on agent's request."""
        # Use instance attribute set by agent node (workaround for state-passing issue)
        doc_ids = self._pending_docs if self._pending_docs else state.get("docs_to_retrieve", [])
        self._pending_docs = []  # Clear for next iteration
        if not doc_ids:
            return {
                "retrieved_docs": [],
                "retrieval_count": state["retrieval_count"] + 1,
            }

        docs = _retrieve_docs(doc_ids)

        return {
            "retrieved_docs": docs,
            "retrieval_count": state["retrieval_count"] + 1,
        }

    def _synthesize(self, state: RAGAgentState) -> dict:
        """Synthesize retrieved documents into context for the agent."""
        docs = state["retrieved_docs"]
        query = state["query"]

        if not docs:
            return {"agent_reasoning": ["No documents retrieved."]}

        docs_text = "\n\n".join(
            f"[{d['doc_id']}]: {d['content']}" for d in docs
        )

        messages = [
            SystemMessage(content=SYNTHESIZE_PROMPT.format(
                query=query, docs=docs_text
            )),
            HumanMessage(content=f"Query: {query}"),
        ]
        response = self.llm.invoke(messages)

        return {"agent_reasoning": [response.content]}

    # -- Graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the RAG-Agent LangGraph."""
        graph = StateGraph(RAGAgentState)

        graph.add_node("agent", self._agent)
        graph.add_node("fetch", self._fetch)
        graph.add_node("synthesize", self._synthesize)

        graph.add_edge(START, "agent")

        graph.add_conditional_edges(
            "agent",
            self._route,
            {
                "retrieve": "fetch",
                "answer": END,
                "max_retrievals": END,
            },
        )

        graph.add_edge("fetch", "synthesize")
        graph.add_edge("synthesize", "agent")

        return graph.compile()

    # -- Convenience runner -------------------------------------------------

    def run(self, query: str, max_retrievals: int | None = None) -> dict:
        """Build the graph, invoke it, and return the final state dict."""
        compiled = self.build_graph()
        max_r = max_retrievals or self.max_retrievals
        result = compiled.invoke(
            {
                "query": query,
                "retrieved_docs": [],
                "agent_reasoning": [],
                "response": "",
                "retrieval_count": 0,
                "max_retrievals": max_r,
                "decision": "",
                "docs_to_retrieve": [],
            }
        )
        return result
