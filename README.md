# 🔀 AgentFlow

**Multi-Agent Collaboration Design Patterns with LangGraph**

AgentFlow is a curated collection of battle-tested multi-agent design patterns built on [LangGraph](https://github.com/langchain-ai/langgraph). Each pattern includes complete code, architecture diagrams, use-case analysis, and performance comparisons.

> **Not a framework.** Not a tutorial collection. This is a **design pattern reference book** for multi-agent systems.

## Why AgentFlow?

Building multi-agent systems is hard. Not because of the tools, but because of the **architecture decisions**:

- When should agents loop vs. terminate?
- How do you coordinate N agents without chaos?
- When is fan-out better than sequential processing?

AgentFlow gives you **proven patterns** you can study, adapt, and combine — each one a complete, runnable example.

## Patterns

| Pattern | Description | Key Technique | Status |
|---------|-------------|---------------|--------|
| [Reflection](patterns/reflection/) | Iterative self-improvement through write → review loops | Conditional looping | ✅ |
| [Debate](patterns/debate/) | Multi-perspective deliberation with moderator synthesis | N-party coordination | ✅ |
| [MapReduce](patterns/map_reduce/) | Parallel fan-out processing with result aggregation | LangGraph Send API | ✅ |
| [Hierarchical](patterns/hierarchical/) | Manager decomposes tasks → Workers execute → Manager aggregates | Nested subgraphs + Send | ✅ |
| [Voting](patterns/voting/) | Multiple agents independently vote, then aggregate | Broadcast fan-out | ✅ |
| [GuardRail](patterns/guardrail/) | Primary agent + safety guard checkpoint | Approve/block/redirect routing | ✅ |
| [RAG-Agent](patterns/rag_agent/) | Agent decides when to retrieve from knowledge base | Conditional retrieval loop | ✅ |

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/agentflow.git
cd agentflow
uv sync
```

### 2. Set up your API key

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 3. Run any pattern

```bash
python patterns/reflection/example.py
python patterns/debate/example.py
python patterns/map_reduce/example.py
python patterns/hierarchical/example.py
python patterns/voting/example.py
python patterns/guardrail/example.py
python patterns/rag_agent/example.py
```

## Project Structure

```
agentflow/
├── patterns/              # Core: one directory per pattern
│   ├── reflection/        # Write → Review loop
│   ├── debate/            # N-party debate + moderator
│   ├── map_reduce/        # Parallel fan-out + reduce
│   ├── hierarchical/      # Manager → Workers → aggregation
│   ├── voting/            # Multi-agent voting + aggregation
│   ├── guardrail/         # Primary + safety checkpoint
│   └── rag_agent/         # Agent with conditional retrieval
├── benchmarks/            # Performance comparison framework
├── docs/                  # Documentation templates
└── tasks/                 # Progress tracking
```

## Requirements

- Python 3.11+
- An OpenAI API key (default model: `gpt-4o-mini`)

## Running Tests

```bash
# Unit tests (no API key needed)
pytest patterns/

# Integration tests (requires OPENAI_API_KEY)
OPENAI_API_KEY=your-key pytest patterns/ -m "not skipif"
```

## Design Philosophy

1. **Patterns, not frameworks** — Each pattern is self-contained. Copy what you need.
2. **Runnable in 3 minutes** — Clone, set API key, run. That's it.
3. **Dual-language docs** — English README + Chinese README for every pattern.
4. **Real LangGraph** — No abstractions over LangGraph. Learn the real API.

## Contributing

See [docs/PATTERN_TEMPLATE.md](docs/PATTERN_TEMPLATE.md) for the pattern documentation template.

## License

MIT
