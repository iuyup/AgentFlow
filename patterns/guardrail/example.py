"""GuardRail Pattern Example -- Safe Content Generation.

Demonstrates a primary agent generating content with a safety guard
checkpoint that can approve, block, or redirect the output.

Usage:
    1. Copy ``.env.example`` to ``.env`` and add your OpenAI API key.
    2. Run::

        python -m patterns.guardrail.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.guardrail.pattern import GuardRailPattern


def main() -> None:
    pattern = GuardRailPattern(max_attempts=3)

    task = (
        "Write a product description for a new AI-powered home security camera. "
        "Highlight its key features: 24/7 monitoring, facial recognition, "
        "two-way audio, and smartphone integration."
    )

    result = pattern.run(task=task)

    # -- Pretty-print results -----------------------------------------------
    print("=" * 60)
    print("GUARDRAIL PATTERN -- Safe Content Generation")
    print("=" * 60)
    print(f"\nTask: {result['task']}")
    print(f"\nAttempts: {result['attempts']}")
    print(f"Guard Verdict: {result['guard_verdict'].upper()}")
    if result["guard_feedback"]:
        print(f"Guard Feedback: {result['guard_feedback']}")
    if result["safety_violations"]:
        print(f"Safety Violations: {result['safety_violations']}")

    print(f"\n{'=' * 60}")
    print("FINAL OUTPUT:")
    print("=" * 60)
    print(result["final_output"])


if __name__ == "__main__":
    main()
