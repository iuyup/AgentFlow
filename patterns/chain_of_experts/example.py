"""Chain-of-Experts Pattern Example.

Run: python patterns/chain_of_experts/example.py
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.chain_of_experts.pattern import ChainOfExpertsPattern


def main() -> None:
    pattern = ChainOfExpertsPattern()

    experts = [
        {
            "name": "Data Scientist",
            "specialty": "Data analysis and machine learning",
            "system_prompt": "Focus on data-driven insights.",
        },
        {
            "name": "Software Architect",
            "specialty": "System design and architecture",
            "system_prompt": "Focus on technical feasibility and scalability.",
        },
        {
            "name": "Product Manager",
            "specialty": "Product strategy and user value",
            "system_prompt": "Focus on market fit and user needs.",
        },
    ]

    result = pattern.run(
        task="Evaluate whether to build an in-house ML platform or use a managed ML service.",
        experts=experts,
    )

    print("=== Final Synthesis ===")
    print(result["final_synthesis"])
    print()
    print(f"Experts consulted: {len(result['expert_outputs'])}")


if __name__ == "__main__":
    main()
