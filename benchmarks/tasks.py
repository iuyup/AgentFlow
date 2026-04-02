"""Standardized benchmark tasks for comparing AgentFlow patterns.

Each task is a structured input paired with the pattern(s) best suited
to solve it.  Run with run_benchmark.py.
"""

from dataclasses import dataclass


@dataclass
class BenchmarkTask:
    """Definition of one benchmark task."""

    name: str
    description: str
    inputs: dict
    applicable_patterns: list[str]


# ---------------------------------------------------------------------------
# Standardized tasks
# ---------------------------------------------------------------------------

NEWS_SUMMARIZATION = BenchmarkTask(
    name="News Summarization",
    description="Collect and synthesize news from 3 different sources on a topic.",
    inputs={
        "topic": "AI coding assistants in 2025",
        "sources": [
            "TechCrunch article on AI tools",
            "Hacker News discussion on AI pair programmers",
            "Arxiv paper on LLM code generation",
        ],
    },
    applicable_patterns=["map_reduce", "reflection"],
)

CODE_REVIEW = BenchmarkTask(
    name="Code Review",
    description="Multi-perspective code review from security, performance, and readability angles.",
    inputs={
        "task": "Review this Python code for security, performance, and readability issues.",
        "code": (
            "def get_user_data(user_id):\n"
            "    import sqlite3\n"
            "    conn = sqlite3.connect('app.db')\n"
            "    cursor = conn.cursor()\n"
            "    cursor.execute(f'SELECT * FROM users WHERE id={user_id}')\n"
            "    return cursor.fetchone()"
        ),
    },
    applicable_patterns=["voting", "debate", "guardrail"],
)

DECISION_MAKING = BenchmarkTask(
    name="Architectural Decision",
    description="Evaluate a technical decision from multiple expert perspectives.",
    inputs={
        "question": "Should we migrate our monolith to microservices? "
        "Consider: team size 5, current deployment weekly, traffic moderate.",
    },
    applicable_patterns=["debate", "voting", "hierarchical"],
)

REFLECTION_WRITING = BenchmarkTask(
    name="Iterative Article Writing",
    description="Write and refine an article through multiple revision cycles.",
    inputs={
        "topic": "The future of AI agents in software development",
    },
    applicable_patterns=["reflection"],
)

RAG_QA = BenchmarkTask(
    name="Knowledge Base Q&A",
    description="Answer questions by retrieving relevant documents from a knowledge base.",
    inputs={
        "query": "What are the best practices for LangGraph state management?",
        "documents": [
            "doc1: LangGraph state management guide",
            "doc2: Best practices for multi-agent systems",
            "doc3: LangGraph checkpointing documentation",
        ],
    },
    applicable_patterns=["rag_agent"],
)

GUARDRAIL_CONTENT = BenchmarkTask(
    name="Safe Content Generation",
    description="Generate content with safety guardrails and quality checks.",
    inputs={
        "task": "Write a technical blog post about AI safety",
    },
    applicable_patterns=["guardrail"],
)

CHAIN_OF_EXPERTS_LEGAL = BenchmarkTask(
    name="Multi-Expert Legal Review",
    description="Sequential expert review for a contract agreement.",
    inputs={
        "task": "Review this software partnership agreement and provide legal, technical, and risk analysis.",
        "experts": [
            {"name": "Legal Expert", "specialty": "contract law"},
            {"name": "Technical Expert", "specialty": "software architecture"},
            {"name": "Risk Analyst", "specialty": "risk assessment"},
        ],
    },
    applicable_patterns=["chain_of_experts"],
)

HUMAN_IN_THE_LOOP_DOCS = BenchmarkTask(
    name="Human-Reviewed Document",
    description="Generate a document that requires human approval before finalization.",
    inputs={
        "task": "Write a formal apology letter to customers for a service outage",
    },
    applicable_patterns=["human_in_the_loop"],
)

SWARM_BRAINSTORM = BenchmarkTask(
    name="Collective Brainstorming",
    description="Multi-agent collective intelligence for creative problem solving.",
    inputs={
        "task": "Brainstorm innovative uses of AI agents in education",
        "agents": [
            {"name": "Educator", "specialty": "pedagogy and learning science"},
            {"name": "Technologist", "specialty": "AI and software"},
            {"name": "Product Designer", "specialty": "user experience"},
        ],
    },
    applicable_patterns=["swarm"],
)


STANDARD_TASKS: list[BenchmarkTask] = [
    NEWS_SUMMARIZATION,
    CODE_REVIEW,
    DECISION_MAKING,
    REFLECTION_WRITING,
    RAG_QA,
    GUARDRAIL_CONTENT,
    CHAIN_OF_EXPERTS_LEGAL,
    HUMAN_IN_THE_LOOP_DOCS,
    SWARM_BRAINSTORM,
]
