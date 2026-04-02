# AgentFlow Pattern Selection Guide

> **How to choose the right multi-agent pattern for your use case.**

This guide provides decision criteria for selecting among AgentFlow's 10 patterns and 2 composite applications.

---

## Quick Decision Tree

```
Is human oversight required for every output?
├── YES --> Human-in-the-Loop
└── NO
    │
    Is the task a single, well-defined objective?
    ├── YES
    │   │
    │   Does it require multiple expert perspectives?
    │   ├── YES --> Chain-of-Experts
    │   └── NO
    │       │
    │       Is output quality more important than speed?
    │       ├── YES --> Reflection
    │       └── NO --> Single Agent (no pattern needed)
    │
    └── NO (complex/multi-faceted task)
        │
        Are there opposing perspectives or trade-offs?
        ├── YES --> Debate
        │
        Does it involve processing many items?
        ├── YES --> MapReduce
        │
        Is there a clear hierarchy (manager/workers)?
        ├── YES --> Hierarchical
        │
        Is collective intelligence/brainstorming needed?
        ├── YES --> Swarm
        │
        Is safety/correctness critical?
        ├── YES --> GuardRail
        │
        Does it need dynamic retrieval during execution?
        └── YES --> RAG-Agent
```

---

## Pattern Overview

### Core Patterns (MVP)

| Pattern | Agents | Best For | Latency | Complexity |
|---------|--------|----------|---------|------------|
| **Reflection** | 2 | Iterative content refinement | Medium | Low |
| **Debate** | 2+ | Exploring opposing viewpoints | Medium-High | Medium |
| **MapReduce** | 1 + N | Parallel data processing | Low (parallel) | Medium |

### Extended Patterns

| Pattern | Agents | Best For | Latency | Complexity |
|---------|--------|----------|---------|------------|
| **Hierarchical** | 1 Manager + N Workers | Task decomposition | Medium | Medium |
| **Voting** | N Voters | Multi-perspective decisions | Low (parallel) | Low |
| **GuardRail** | 1 + Safety Check | High-stakes output validation | Medium | Low |
| **RAG-Agent** | 1 + Retrieval | Knowledge-intensive tasks | Medium | Medium |

### Advanced Patterns

| Pattern | Agents | Best For | Latency | Complexity |
|---------|--------|----------|---------|------------|
| **Chain-of-Experts** | N Experts + Synthesizer | Sequential multi-domain analysis | Medium | Medium |
| **Human-in-the-Loop** | 1 + Human Reviewer | Compliance-required approvals | High | Low |
| **Swarm** | N Peers | Collective intelligence | Medium-High | Medium-High |

---

## Detailed Pattern Descriptions

### Reflection — Iterative Self-Improvement

**Use when:** You need to produce and refine a single text artifact (article, email, report) where each iteration meaningfully improves quality.

**Don't use when:** The task has a definitive correct answer, requires external knowledge, or needs multiple domain perspectives.

**Key characteristics:**
- Writer + Reviewer loop
- Numeric scoring (0-10)
- Configurable threshold and max iterations

**Example tasks:**
- Drafting a business proposal
- Refining technical documentation
- Iterative code review with self-critique

---

### Debate — Adversarial Exploration

**Use when:** You need to explore genuinely opposing viewpoints on a decision, policy, or architectural choice.

**Don't use when:** There's no meaningful opposition to explore, or you need fast single-perspective analysis.

**Key characteristics:**
- N debaters with different perspectives
- Moderator synthesizes and decides settlement
- Configurable max rounds

**Example tasks:**
- Investment decision analysis
- Architectural trade-off debates
- Policy impact assessment

---

### MapReduce — Parallel Processing

**Use when:** You need to process many independent items (sources, documents, data points) and combine results.

**Don't use when:** Items have dependencies, or order of processing matters.

**Key characteristics:**
- Fan-out to N mappers in parallel
- Sequential reducer combines outputs
- Linear scaling with item count

**Example tasks:**
- Multi-source news aggregation
- Parallel document analysis
- Batch data enrichment

---

### Hierarchical — Manager-Worker Decomposition

**Use when:** A complex task can be cleanly decomposed into independent subtasks, each handled by a specialized worker.

**Don't use when:** Subtasks are highly interdependent, or decomposition itself requires iterative refinement.

**Key characteristics:**
- Central manager controls flow
- Parallel worker execution via Send API
- Manager aggregates final results

**Example tasks:**
- Research across multiple dimensions
- Multi-faceted business analysis
- Parallel code generation by specialty

---

### Voting — Collective Decision Making

**Use when:** You need a decision from multiple independent experts with different areas of expertise, and want to aggregate their judgments.

**Don't use when:** Experts need to build on each other (use Chain-of-Experts), or you need adversarial exploration (use Debate).

**Key characteristics:**
- N independent voters
- Optional weighting by expertise
- Aggregator synthesizes decisions

**Example tasks:**
- Security + Performance + Maintainability code review
- Multi-criteria decision analysis
- Expert panel recommendations

---

### GuardRail — Safety Validation

**Use when:** You need to validate outputs against safety, policy, or quality guidelines before finalization.

**Don't use when:** No external validation needed, or validation is part of a larger pipeline (use composite instead).

**Key characteristics:**
- Primary agent generates output
- Guard validates against rules
- Configurable retry on rejection

**Example tasks:**
- Content safety screening
- Policy compliance checking
- Quality gate in pipelines

---

### RAG-Agent — Retrieval-Augmented Generation

**Use when:** Tasks require dynamic retrieval of documents or knowledge during execution, not just at the start.

**Don't use when:** All required knowledge is in the prompt, or retrieval is a one-time step before generation.

**Key characteristics:**
- Agent decides when to retrieve
- Conditional branching on retrieval need
- Configurable max retrieval rounds

**Example tasks:**
- Question answering over knowledge base
- Document-grounded analysis
- Contextual research tasks

---

### Chain-of-Experts — Sequential Expertise Building

**Use when:** Each expert needs to see the previous expert's analysis, building a cumulative body of work.

**Don't use when:** Experts can work independently (use Voting), or you need adversarial debate (use Debate).

**Key characteristics:**
- Sequential expert processing
- Each expert sees all previous outputs
- Final synthesizer integrates all perspectives

**Example tasks:**
- Legal + Technical + Risk review chain
- Document editing with specialist passes
- Multi-stage analysis (feasibility → risk → mitigation)

---

### Human-in-the-Loop — Human Approval Checkpoints

**Use when:** Human approval is mandatory before final output — compliance, high-stakes decisions, or editorial workflows.

**Don't use when:** Fully automated execution is acceptable, or human involvement would create unacceptable latency.

**Key characteristics:**
- Primary agent generates output
- Human reviewer approves/rejects/redirects
- Configurable max attempts

**Example tasks:**
- Legal document approval
- Customer-facing communication review
- Financial report sign-off

---

### Swarm — Decentralized Collective Intelligence

**Use when:** You need diverse agents to collaborate as peers, sharing information and building on each other without central coordination.

**Don't use when:** You need strict control flow, sequential processing, or clear authority hierarchy.

**Key characteristics:**
- Peer-to-peer agent communication
- Multiple collaboration rounds
- Aggregator synthesizes collective output

**Example tasks:**
- Collective brainstorming
- Multi-perspective research synthesis
- Creative problem exploration

---

## Composite Applications

### AI Newsroom

**Combines:** MapReduce + Debate + Reflection

**Use when:** You need to produce a polished, balanced article from multiple sources, with editorial oversight.

**Structure:**
1. Collect news from multiple sources (MapReduce)
2. Debate pro/con angles (Debate)
3. Polish final article (Reflection)

### Research Team

**Combines:** Hierarchical + RAG-Agent + GuardRail

**Use when:** You need comprehensive research with safety validation.

**Structure:**
1. Decompose question (Hierarchical manager)
2. Research each sub-question (Workers)
3. Synthesize into report
4. Validate safety and accuracy (GuardRail)

---

## Performance Considerations

| Pattern | Parallelism | LLM Calls | Typical Latency |
|---------|-----------|-----------|----------------|
| Reflection | Sequential | O(iterations × 2) | Medium |
| Debate | Sequential | O(rounds × debaters + moderator) | Medium-High |
| MapReduce | Full parallel | O(N mappers + 1 reducer) | Low |
| Hierarchical | Worker parallel | O(workers + manager) | Medium |
| Voting | Full parallel | O(N voters + aggregator) | Low |
| GuardRail | Sequential | O(attempts × 2) | Medium |
| RAG-Agent | Sequential | O(retrievals + synthesis) | Medium |
| Chain-of-Experts | Sequential | O(N experts + synthesizer) | Medium |
| Human-in-the-Loop | Sequential | O(attempts × 2) | High |
| Swarm | Limited parallel | O(rounds × N agents + aggregator) | Medium-High |

---

## Anti-Patterns: When NOT to Use Multi-Agent

- **Single, simple task** → Just use a single LLM call
- **Tasks with strict ordering** → Don't force parallelization
- **Real-time requirements** → Multi-agent adds latency; consider caching or simpler patterns
- **Over-engineering** → A single well-crafted prompt often beats multiple agents
