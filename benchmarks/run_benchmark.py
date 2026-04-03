"""Benchmark runner for AgentFlow patterns.

Compares multiple patterns on standardized tasks, measuring:
- LLM call count
- Execution time
- Output quality (via LLM judge)

Usage:
    # Requires OPENAI_API_KEY
    python benchmarks/run_benchmark.py

    # Or with specific API key
    OPENAI_API_KEY=sk-... python benchmarks/run_benchmark.py
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from agentflow.utils import (
    LLMCallCounterHandler,
    get_llm_call_count,
    reset_llm_count,
)

# Handler registry so we can read counts after each run
_handler_registry: dict[str, LLMCallCounterHandler] = {}

# ---------------------------------------------------------------------------
# Pattern registry — import all patterns here
# ---------------------------------------------------------------------------

PATTERNRegistry: dict[str, type] = {}


def _lazy_import_patterns():
    """Lazily import all patterns to avoid heavy startup cost."""
    global PATTERNRegistry
    if PATTERNRegistry:
        return

    try:
        from patterns.reflection.pattern import ReflectionPattern
        from patterns.debate.pattern import DebatePattern
        from patterns.map_reduce.pattern import MapReducePattern
        from patterns.hierarchical.pattern import HierarchicalPattern
        from patterns.voting.pattern import VotingPattern
        from patterns.guardrail.pattern import GuardRailPattern
        from patterns.rag_agent.pattern import RAGAgentPattern
        from patterns.chain_of_experts.pattern import ChainOfExpertsPattern
        from patterns.human_in_the_loop.pattern import HumanInTheLoopPattern
        from patterns.swarm.pattern import SwarmPattern

        PATTERNRegistry.update({
            "reflection": ReflectionPattern,
            "debate": DebatePattern,
            "map_reduce": MapReducePattern,
            "hierarchical": HierarchicalPattern,
            "voting": VotingPattern,
            "guardrail": GuardRailPattern,
            "rag_agent": RAGAgentPattern,
            "chain_of_experts": ChainOfExpertsPattern,
            "human_in_the_loop": HumanInTheLoopPattern,
            "swarm": SwarmPattern,
        })
    except ImportError as e:
        raise RuntimeError(f"Failed to import patterns: {e}")


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    task_name: str
    pattern_name: str
    llm_call_count: int
    elapsed_seconds: float
    output_length: int
    output_preview: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Pattern runners — map pattern names to their run() signatures
# ---------------------------------------------------------------------------


def _run_reflection(inputs: dict) -> dict:
    global _handler_registry
    from patterns.reflection.pattern import ReflectionPattern
    handler = LLMCallCounterHandler()
    _handler_registry["reflection"] = handler
    pattern = ReflectionPattern(max_iterations=2, score_threshold=5.0, counter_handler=handler)
    return pattern.run(topic=inputs["topic"])


def _run_debate(inputs: dict) -> dict:
    global _handler_registry
    from patterns.debate.pattern import DebatePattern
    handler = LLMCallCounterHandler()
    _handler_registry["debate"] = handler
    pattern = DebatePattern(max_rounds=2, counter_handler=handler)
    debaters = [
        {
            "name": "Advocate",
            "role": "Supporter of the decision",
            "system_prompt": "Argue in favor of the proposed decision.",
        },
        {
            "name": "Critic",
            "role": "Opponent of the decision",
            "system_prompt": "Argue against the proposed decision.",
        },
    ]
    return pattern.run(topic=inputs["question"], debaters=debaters)


def _run_map_reduce(inputs: dict) -> dict:
    global _handler_registry
    from patterns.map_reduce.pattern import MapReducePattern
    handler = LLMCallCounterHandler()
    _handler_registry["map_reduce"] = handler
    pattern = MapReducePattern(counter_handler=handler)
    return pattern.run(topic=inputs["topic"], sources=inputs["sources"])


def _run_hierarchical(inputs: dict) -> dict:
    global _handler_registry
    from patterns.hierarchical.pattern import HierarchicalPattern
    handler = LLMCallCounterHandler()
    _handler_registry["hierarchical"] = handler
    pattern = HierarchicalPattern(counter_handler=handler)
    return pattern.run(task=inputs["question"])


def _run_voting(inputs: dict) -> dict:
    global _handler_registry
    from patterns.voting.pattern import VotingPattern
    handler = LLMCallCounterHandler()
    _handler_registry["voting"] = handler
    pattern = VotingPattern(counter_handler=handler)
    voters = [
        {"name": "Security Expert", "expertise": "Security analysis"},
        {"name": "Performance Expert", "expertise": "Performance optimization"},
        {"name": "Maintainability Expert", "expertise": "Code maintainability"},
    ]
    return pattern.run(question=inputs["question"], voters=voters)


def _run_guardrail(inputs: dict) -> dict:
    global _handler_registry
    from patterns.guardrail.pattern import GuardRailPattern
    handler = LLMCallCounterHandler()
    _handler_registry["guardrail"] = handler
    pattern = GuardRailPattern(max_attempts=2, counter_handler=handler)
    return pattern.run(task=inputs["task"])


def _run_rag_agent(inputs: dict) -> dict:
    global _handler_registry
    from patterns.rag_agent.pattern import RAGAgentPattern
    handler = LLMCallCounterHandler()
    _handler_registry["rag_agent"] = handler
    pattern = RAGAgentPattern(max_retrievals=2, counter_handler=handler)
    return pattern.run(query=inputs["query"])


def _run_chain_of_experts(inputs: dict) -> dict:
    global _handler_registry
    from patterns.chain_of_experts.pattern import ChainOfExpertsPattern
    handler = LLMCallCounterHandler()
    _handler_registry["chain_of_experts"] = handler
    pattern = ChainOfExpertsPattern(counter_handler=handler)
    return pattern.run(task=inputs["task"], experts=inputs["experts"])


def _run_human_in_the_loop(inputs: dict) -> dict:
    global _handler_registry
    from patterns.human_in_the_loop.pattern import HumanInTheLoopPattern
    handler = LLMCallCounterHandler()
    _handler_registry["human_in_the_loop"] = handler
    pattern = HumanInTheLoopPattern(max_attempts=2, counter_handler=handler)
    return pattern.run(task=inputs["task"])


def _run_swarm(inputs: dict) -> dict:
    global _handler_registry
    from patterns.swarm.pattern import SwarmPattern
    handler = LLMCallCounterHandler()
    _handler_registry["swarm"] = handler
    pattern = SwarmPattern(max_rounds=2, counter_handler=handler)
    return pattern.run(task=inputs["task"], agents=inputs["agents"])


PATTERN_RUNNERS: dict[str, callable] = {
    "reflection": _run_reflection,
    "debate": _run_debate,
    "map_reduce": _run_map_reduce,
    "hierarchical": _run_hierarchical,
    "voting": _run_voting,
    "guardrail": _run_guardrail,
    "rag_agent": _run_rag_agent,
    "chain_of_experts": _run_chain_of_experts,
    "human_in_the_loop": _run_human_in_the_loop,
    "swarm": _run_swarm,
}


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


class BenchmarkRunner:
    """Run benchmarks across tasks and patterns."""

    def __init__(self, tasks: list):
        self.tasks = tasks
        self.results: list[BenchmarkResult] = []

    def run_task_pattern(self, task, pattern_name: str) -> BenchmarkResult:
        """Run one (task, pattern) combination."""
        runner = PATTERN_RUNNERS.get(pattern_name)
        if not runner:
            return BenchmarkResult(
                task_name=task.name,
                pattern_name=pattern_name,
                llm_call_count=0,
                elapsed_seconds=0.0,
                output_length=0,
                output_preview="",
                error=f"No runner for pattern: {pattern_name}",
            )

        start = time.perf_counter()
        try:
            result = runner(task.inputs)
            elapsed = time.perf_counter() - start

            # Extract output from result dict
            output = _extract_output(result, pattern_name)
            handler = _handler_registry.get(pattern_name)
            llm_count = result.get("llm_call_count", get_llm_call_count(handler) if handler else 0)
            return BenchmarkResult(
                task_name=task.name,
                pattern_name=pattern_name,
                llm_call_count=llm_count,
                elapsed_seconds=elapsed,
                output_length=len(output),
                output_preview=output[:200],
                error=None,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            return BenchmarkResult(
                task_name=task.name,
                pattern_name=pattern_name,
                llm_call_count=0,
                elapsed_seconds=elapsed,
                output_length=0,
                output_preview="",
                error=str(e),
            )

    def run_all(self) -> list[BenchmarkResult]:
        """Run all applicable (task, pattern) combinations."""
        self.results = []
        for task in self.tasks:
            for pattern_name in task.applicable_patterns:
                if pattern_name not in PATTERN_RUNNERS:
                    continue
                print(f"  Running {task.name} with {pattern_name}...", end=" ")
                result = self.run_task_pattern(task, pattern_name)
                status = "ERROR" if result.error else "OK"
                print(f"[{status}] {result.elapsed_seconds:.1f}s")
                self.results.append(result)
        return self.results

    def to_markdown(self) -> str:
        """Format results as a Markdown table."""
        lines = [
            "# AgentFlow Benchmark Results",
            f"\nGenerated: {datetime.now().isoformat()}\n",
            "| Task | Pattern | LLM Calls | Time (s) | Output Len | Error |",
            "|------|---------|-----------|----------|------------|-------|",
        ]
        for r in self.results:
            err = r.error[:30] + "..." if r.error and len(r.error) > 30 else (r.error or "")
            lines.append(
                f"| {r.task_name} | {r.pattern_name} | "
                f"{r.llm_call_count} | {r.elapsed_seconds:.2f} | "
                f"{r.output_length} | {err} |"
            )
        return "\n".join(lines)

    def to_csv(self) -> str:
        """Format results as CSV."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "task", "pattern", "llm_calls", "elapsed_seconds",
            "output_length", "output_preview", "error",
        ])
        for r in self.results:
            writer.writerow([
                r.task_name, r.pattern_name, r.llm_call_count,
                f"{r.elapsed_seconds:.3f}", r.output_length,
                r.output_preview[:100], r.error or "",
            ])
        return output.getvalue()

    def save_results(self, results_dir: Path = Path("benchmarks/results")):
        """Save results to timestamped files."""
        results_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_path = results_dir / f"benchmark_{stamp}.md"
        csv_path = results_dir / f"benchmark_{stamp}.csv"
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        csv_path.write_text(self.to_csv(), encoding="utf-8")
        print(f"\nResults saved to:\n  {md_path}\n  {csv_path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_output(result: dict, pattern_name: str) -> str:
    """Extract the main output string from a pattern result dict."""
    key_map = {
        "reflection": "draft",
        "debate": "final_decision",
        "map_reduce": "final_summary",
        "hierarchical": "final_result",
        "voting": "aggregated_result",
        "guardrail": "final_output",
        "rag_agent": "response",
        "chain_of_experts": "final_synthesis",
        "human_in_the_loop": "final_output",
        "swarm": "final_conclusion",
    }
    key = key_map.get(pattern_name, "")
    return result.get(key, str(result))[:1000]

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_dotenv()

    import os

    if not os.getenv("OPENAI_API_KEY") and not os.getenv("DEEPSEEK_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY or DEEPSEEK_API_KEY before running benchmarks.")
        raise SystemExit(1)

    from benchmarks.tasks import STANDARD_TASKS

    _lazy_import_patterns()

    print("AgentFlow Benchmark Runner")
    print("=" * 50)
    print(f"Tasks: {len(STANDARD_TASKS)}")
    print(f"Patterns: {len(PATTERN_RUNNERS)}")
    print()

    runner = BenchmarkRunner(tasks=STANDARD_TASKS)
    runner.run_all()
    runner.save_results()

    print("\n" + runner.to_markdown())
