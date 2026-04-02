"""Swarm Pattern Example.

Run: python patterns/swarm/example.py
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.swarm.pattern import SwarmPattern


def main() -> None:
    pattern = SwarmPattern(max_rounds=2)

    agents = [
        {"name": "Strategist", "specialty": "Strategic planning"},
        {"name": "Technologist", "specialty": "Technology trends"},
        {"name": "Economist", "specialty": "Market economics"},
    ]

    result = pattern.run(
        task="What will be the most impactful technology trend of 2026?",
        agents=agents,
    )

    print("=== Collective Conclusion ===")
    print(result["final_conclusion"])
    print()
    print(f"Rounds: {result['rounds']}")
    print(f"Messages: {len(result['messages'])}")


if __name__ == "__main__":
    main()
