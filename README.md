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
| [Reflection](web/docs/patterns/reflection/) | Iterative self-improvement through write → review loops | Conditional looping | ✅ |
| [Debate](web/docs/patterns/debate/) | Multi-perspective deliberation with moderator synthesis | N-party coordination | ✅ |
| [MapReduce](web/docs/patterns/map_reduce/) | Parallel fan-out processing with result aggregation | LangGraph Send API | ✅ |
| [Hierarchical](web/docs/patterns/hierarchical/) | Manager decomposes tasks → Workers execute → Manager aggregates | Nested subgraphs + Send | ✅ |
| [Voting](web/docs/patterns/voting/) | Multiple agents independently vote, then aggregate | Broadcast fan-out | ✅ |
| [GuardRail](web/docs/patterns/guardrail/) | Primary agent + safety guard checkpoint | Approve/block/redirect routing | ✅ |
| [RAG-Agent](web/docs/patterns/rag_agent/) | Agent decides when to retrieve from knowledge base | Conditional retrieval loop | ✅ |
| [Chain-of-Experts](web/docs/patterns/chain_of_experts/) | Task passes through specialized agents in sequence | Sequential routing | ✅ |
| [Human-in-the-Loop](web/docs/patterns/human_in_the_loop/) | Key nodes wait for human confirmation | Interrupt + resume | ✅ |
| [Swarm](web/docs/patterns/swarm/) | Decentralized multi-agent collaboration | Dynamic orchestration | ✅ |

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
python -m agentflow.patterns.reflection.example
python -m agentflow.patterns.debate.example
python -m agentflow.patterns.map_reduce.example
```

### 4. Browse documentation

```bash
cd web
pip install -r requirements.txt
python sync_docs.py
mkdocs serve
# Visit http://localhost:8000
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
│   ├── rag_agent/         # Agent with conditional retrieval
│   ├── chain_of_experts/  # Sequential expert routing
│   ├── human_in_the_loop/ # Human interruption
│   └── swarm/             # Decentralized orchestration
├── web/                   # Documentation site (MkDocs)
│   ├── docs/             # Documentation source
│   ├── mkdocs.yml        # Site configuration
│   └── sync_docs.py      # Pattern doc sync script
├── benchmarks/            # Performance comparison framework
└── tasks/                 # Progress tracking
```

## Documentation Site

The documentation site is built with **MkDocs + Material** and deployed at `web/`:

```bash
# Local preview
cd web
pip install -r requirements.txt
python sync_docs.py    # Sync pattern docs
mkdocs serve          # Visit http://localhost:8000

# Build static site
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
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

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT
