"""Human-in-the-Loop Pattern Example.

Run: python patterns/human_in_the_loop/example.py
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.human_in_the_loop.pattern import HumanInTheLoopPattern


def main() -> None:
    pattern = HumanInTheLoopPattern(max_attempts=2)

    result = pattern.run(
        task="Write a brief technical overview of LangGraph's core concepts "
        "including StateGraph, nodes, edges, and conditional edges."
    )

    print("=== Final Output ===")
    print(result["final_output"])
    print()
    print(f"Attempts: {result['attempts']}")
    print(f"Human verdict: {result['human_verdict']}")


if __name__ == "__main__":
    main()
