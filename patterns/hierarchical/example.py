"""Hierarchical Pattern Example -- AI Industry Analysis.

Demonstrates a Manager agent decomposing a complex research task into
subtasks for parallel Worker agents, then synthesizing their findings.

Usage:
    1. Copy ``.env.example`` to ``.env`` and add your OpenAI API key.
    2. Run::

        python -m patterns.hierarchical.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.hierarchical.pattern import HierarchicalPattern


def main() -> None:
    pattern = HierarchicalPattern()

    result = pattern.run(
        task="Analyze the current state and future prospects of the AI industry, "
        "covering technology trends, market dynamics, competitive landscape, "
        "regulatory environment, and investment outlook."
    )

    # -- Pretty-print results -----------------------------------------------
    print("=" * 60)
    print("HIERARCHICAL PATTERN -- AI Industry Analysis")
    print("=" * 60)
    print(f"\nOriginal Task: {result['task']}")
    print(f"\nDecomposed into {len(result['decomposed_tasks'])} subtasks:")
    for task in result["decomposed_tasks"]:
        print(f"  - [{task['task_id']}] {task.get('title', task.get('objective', ''))}")

    print(f"\n{'=' * 60}")
    print("WORKER RESULTS:")
    print("=" * 60)
    for r in result["worker_results"]:
        print(f"\n>>> {r['task_id']}: {r['subtask']}")
        print(f"    {r['result'][:300]}...")

    print(f"\n{'=' * 60}")
    print("FINAL SYNTHESIS (Manager Aggregate):")
    print("=" * 60)
    print(result["final_result"])


if __name__ == "__main__":
    main()
