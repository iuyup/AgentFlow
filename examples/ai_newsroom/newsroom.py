"""AI Newsroom — Multi-stage news production pipeline.

Combines: MapReduce + Debate + Reflection
"""

from typing import Optional

from langchain_core.language_models import BaseChatModel

from agentflow.utils import get_default_llm as _default_llm

from langgraph.graph import END, START, StateGraph

import operator
from typing import Annotated, TypedDict


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class NewsroomState(TypedDict):
    """State flowing through the newsroom pipeline."""

    topic: str
    sources: list[str]
    collected_news: Annotated[list[dict], operator.add]  # from MapReduce
    debate_history: list[dict]  # from Debate
    final_decision: str  # from Debate moderator
    polished_article: str  # final output after Reflection
    reflection_score: float


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

COLLECT_SYSTEM_PROMPT = (
    "You are a news journalist. Given a topic and a source description, "
    "write a brief 2-paragraph news article covering this topic from that source's perspective. "
    "Be factual, balanced, and newsworthy."
)

DEBATE_ADVOCATE_PROMPT = (
    "You are a investigative journalist advocate. "
    "Analyze the collected news articles and argue FOR the topic's significance and implications. "
    "Use specific facts from the articles."
)

DEBATE_CRITIC_PROMPT = (
    "You are a skeptical editor. "
    "Analyze the collected news articles and present critical counterpoints, "
    "potential biases, or missing context. "
    "Use specific facts from the articles."
)

MODERATOR_PROMPT = (
    "You are the editor-in-chief. Review the pro and con arguments about:\n\n"
    "{debate_summary}\n\n"
    "Determine the key takeaways and write a balanced 2-paragraph editorial conclusion."
)

WRITER_PROMPT = (
    "You are a senior editor polishing a news article. "
    "Based on the moderator's editorial guidance and the original news, "
    "produce a final polished news article. "
    "It should be well-structured, engaging, and ready for publication."
)

REVIEWER_PROMPT = (
    "You are a quality editor reviewing an article. "
    "Score it 1-10 on clarity, factual accuracy, and engagement. "
    "Format: Score: X/10 with brief comments."
)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class AINewsroom:
    """Multi-stage newsroom combining MapReduce + Debate + Reflection.

    Graph topology:

        START --> collect_news --> debate --> polish --> END
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
    ):
        self.llm = llm or _default_llm(model)

    # -- Node: collect news from multiple sources (MapReduce-style) -----------

    def _collect_news(self, state: NewsroomState) -> dict:
        """Collect news from all sources in parallel (simulated)."""
        from langgraph.types import Send

        return [
            Send(
                "news_worker",
                {"source": source, "topic": state["topic"]}
            )
            for source in state["sources"]
        ]

    def _news_worker(self, state: NewsroomState) -> dict:
        """One worker collects news from one source."""
        source = state["source"]
        topic = state["topic"]

        messages = [
            ("system", COLLECT_SYSTEM_PROMPT),
            ("user", f"Topic: {topic}\nSource: {source}"),
        ]
        from langchain_core.messages import HumanMessage, SystemMessage
        msgs = [
            SystemMessage(content=COLLECT_SYSTEM_PROMPT),
            HumanMessage(content=f"Topic: {topic}\nSource: {source}"),
        ]
        response = self.llm.invoke(msgs)

        return {
            "collected_news": [{
                "source": source,
                "article": response.content,
            }]
        }

    def _aggregate_news(self, state: NewsroomState) -> dict:
        """Aggregate all collected news into a summary."""
        summary = "\n\n".join(
            f"### {n['source']}\n{n['article']}"
            for n in state["collected_news"]
        )
        return {"collected_news_summary": summary}

    # -- Node: debate pro/con ------------------------------------------------

    def _debate(self, state: NewsroomState) -> dict:
        """Run a 2-person debate (advocate vs critic) on the topic."""
        from langchain_core.messages import HumanMessage, SystemMessage

        news_summary = "\n\n".join(
            f"### {n['source']}\n{n['article']}"
            for n in state["collected_news"]
        )

        # Advocate
        advocate_messages = [
            SystemMessage(content=DEBATE_ADVOCATE_PROMPT),
            HumanMessage(content=f"Topic: {state['topic']}\n\nNews:\n{news_summary}"),
        ]
        advocate_response = self.llm.invoke(advocate_messages)

        # Critic
        critic_messages = [
            SystemMessage(content=DEBATE_CRITIC_PROMPT),
            HumanMessage(content=f"Topic: {state['topic']}\n\nNews:\n{news_summary}"),
        ]
        critic_response = self.llm.invoke(critic_messages)

        return {
            "debate_history": [
                {"speaker": "Advocate", "argument": advocate_response.content},
                {"speaker": "Critic", "argument": critic_response.content},
            ],
        }

    def _moderator(self, state: NewsroomState) -> dict:
        """Editor-in-chief synthesizes debate into editorial conclusion."""
        from langchain_core.messages import HumanMessage, SystemMessage

        debate_text = "\n\n".join(
            f"### {d['speaker']}\n{d['argument']}"
            for d in state["debate_history"]
        )

        messages = [
            SystemMessage(content=MODERATOR_PROMPT.format(debate_summary=debate_text)),
            HumanMessage(content=f"Topic: {state['topic']}"),
        ]
        response = self.llm.invoke(messages)

        return {"final_decision": response.content}

    # -- Node: reflection polish ---------------------------------------------

    def _write_article(self, state: NewsroomState) -> dict:
        """Polish the article using reflection loop."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=WRITER_PROMPT),
            HumanMessage(
                content=(
                    f"Topic: {state['topic']}\n\n"
                    f"Editorial guidance:\n{state['final_decision']}\n\n"
                    f"Original news articles:\n"
                    + "\n\n".join(f"### {n['source']}\n{n['article']}" for n in state["collected_news"])
                )
            ),
        ]
        response = self.llm.invoke(messages)

        return {
            "polished_article": response.content,
            "history": [response.content],
        }

    def _review_article(self, state: NewsroomState) -> dict:
        """Review the article and score it."""
        import re
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(content=state["polished_article"]),
        ]
        response = self.llm.invoke(messages)

        match = re.search(r"(\d+(?:\.\d+)?)\s*/?\s*10", response.content)
        score = float(match.group(1)) if match else 5.0

        return {"feedback": response.content, "score": score}

    def _should_revise(self, state: NewsroomState) -> str:
        """Continue revising until score >= 7.0 or max iterations."""
        if state.get("iteration", 0) >= 2:
            return "end"
        if state.get("score", 0) >= 7.0:
            return "end"
        return "continue"

    # -- Graph construction -------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Build the full newsroom pipeline graph."""
        graph = StateGraph(NewsroomState)

        # MapReduce-style collection
        graph.add_node("news_worker", self._news_worker)
        graph.add_node("aggregate_news", self._aggregate_news)

        # Debate
        graph.add_node("debate", self._debate)
        graph.add_node("moderator", self._moderator)

        # Reflection polish
        graph.add_node("write_article", self._write_article)
        graph.add_node("review_article", self._review_article)

        # Edges
        graph.add_edge(START, "news_worker")
        graph.add_edge("news_worker", "aggregate_news")
        graph.add_edge("aggregate_news", "debate")
        graph.add_edge("debate", "moderator")
        graph.add_edge("moderator", "write_article")
        graph.add_edge("write_article", "review_article")

        graph.add_conditional_edges(
            "review_article",
            self._should_revise,
            {
                "continue": "write_article",
                "end": END,
            },
        )

        return graph.compile()

    def run(self, topic: str, sources: list[str]) -> dict:
        """Run the full newsroom pipeline."""
        compiled = self.build_graph()
        result = compiled.invoke({
            "topic": topic,
            "sources": sources,
            "collected_news": [],
            "debate_history": [],
            "final_decision": "",
            "polished_article": "",
            "reflection_score": 0.0,
            "iteration": 0,
            "feedback": "",
            "history": [],
            "score": 0.0,
        })
        return result
