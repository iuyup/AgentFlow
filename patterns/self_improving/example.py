"""Self-Improving Pattern Example -- Watch an agent build its skill library.

The demo runs five tasks back-to-back. Tasks 1 & 5 are both complexity
analyses, and tasks 2-4 are all code reviews -- so by the second time the
agent sees a similar task it should match an existing skill and reuse it.

Run:
    uv run python -m patterns.self_improving.example
"""

from __future__ import annotations

import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from patterns.self_improving.pattern import MemoryStore, SelfImprovingPattern


def main() -> None:
    # Start from a clean slate so the demo is reproducible. In real use,
    # you'd KEEP the storage_dir around -- that's the whole point.
    demo_dir = "./.demo_self_improving_memory"
    if Path(demo_dir).exists():
        shutil.rmtree(demo_dir)

    pattern = SelfImprovingPattern(
        storage_dir=demo_dir,
        nudge_interval=3,  # consolidate memory every 3 tasks for the demo
    )

    tasks = [
        "Analyze the time complexity of quicksort and explain when it degrades to O(n^2).",
        "Review this Python function for bugs: def fib(n): return fib(n-1) + fib(n-2)",
        "Write a comprehensive code review for a REST API endpoint that handles user authentication.",
        "Review this code for security issues: user_input = request.args.get('q'); db.execute(f\"SELECT * FROM users WHERE name={user_input}\")",
        "Analyze the space complexity of merge sort and compare it with quicksort.",
    ]

    print("=" * 60)
    print("SELF-IMPROVING PATTERN -- skill library demo")
    print("=" * 60)

    task_count = 0
    for i, task in enumerate(tasks, start=1):
        print(f"\nTask {i}: {task[:80]}{'...' if len(task) > 80 else ''}")
        print("-" * 60)

        result = pattern.run(task, task_count=task_count)
        task_count = result["task_count"]

        used = result["matched_skill"]["name"] if result.get("matched_skill") else "None"
        print(f"  task_type    : {result['task_type']}")
        print(f"  score        : {result['evaluation_score']}/10")
        print(f"  used skill   : {used}")
        print(f"  steps logged : {len(result['execution_steps'])}")

    # Show what the agent learned across the session.
    store = MemoryStore(demo_dir)
    print(f"\n{'=' * 60}")
    print("Final agent state")
    print("=" * 60)

    print("\nSkills learned:")
    skills = store.get_skill_index()
    if not skills:
        print("  (no skills extracted -- try lowering skill_threshold)")
    for s in skills:
        print(
            f"  - {s['name']}: {s['description']} "
            f"(used {s['use_count']}x, avg {s['avg_score']})"
        )

    print("\nPersistent hot memory:")
    print(store.get_memory_snapshot())


if __name__ == "__main__":
    main()
