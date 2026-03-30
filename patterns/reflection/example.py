"""Reflection Pattern Example -- AI Article Writing with Self-Improvement.

Run:
    uv run python -m patterns.reflection.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.reflection.pattern import ReflectionPattern


def main():
    pattern = ReflectionPattern(max_iterations=3, score_threshold=8.0)

    result = pattern.run("The Future of AI Agents in Software Development")

    print("=" * 60)
    print("REFLECTION PATTERN -- AI Article Writer")
    print("=" * 60)
    print(f"\nTopic: {result['topic']}")
    print(f"Iterations: {result['iteration']}")
    print(f"Final Score: {result['score']}/10")
    print(f"\n{'=' * 60}")
    print("FINAL DRAFT:")
    print("=" * 60)
    print(result["draft"])

    if result.get("history"):
        print(f"\n{'=' * 60}")
        print(f"Revision History: {len(result['history'])} drafts written")
        for i, draft in enumerate(result["history"], 1):
            print(f"\n--- Draft {i} (first 200 chars) ---")
            print(draft[:200] + "...")


if __name__ == "__main__":
    main()
