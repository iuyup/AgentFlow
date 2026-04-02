"""Voting Pattern Example -- Technology Stack Decision.

Demonstrates multiple expert agents independently voting on a technology
decision, with weighted aggregation based on expertise.

Usage:
    1. Copy ``.env.example`` to ``.env`` and add your OpenAI API key.
    2. Run::

        python -m patterns.voting.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.voting.pattern import VotingPattern


def main() -> None:
    voters = [
        {"name": "CTO", "expertise": "System Architecture and Scalability"},
        {"name": "Security Expert", "expertise": "Application Security and Compliance"},
        {"name": "DevOps Lead", "expertise": "CI/CD, Infrastructure, and Operations"},
        {"name": "Product Manager", "expertise": "User Experience and Time-to-Market"},
    ]

    question = (
        "Our startup is building a new data-intensive SaaS product. "
        "We need to choose between:\n"
        "A) PostgreSQL + Python/FastAPI (mature, well-understood stack)\n"
        "B) MongoDB + Node.js (flexible schema, faster initial development)\n"
        "C) Neon (serverless Postgres) + Go (modern, high performance)\n\n"
        "What is the best choice considering our team of 5 engineers, "
        "3-month MVP deadline, and potential for 10x user growth?"
    )

    pattern = VotingPattern()
    result = pattern.run(
        question=question,
        voters=voters,
        voting_strategy="weighted",
    )

    # -- Pretty-print results -----------------------------------------------
    print("=" * 60)
    print("VOTING PATTERN -- Technology Stack Decision")
    print("=" * 60)
    print(f"\nQuestion: {result['question']}")
    print(f"\nVoters ({len(result['voters'])}):")
    for v in result["voters"]:
        print(f"  - {v['name']}: {v['expertise']}")
    print(f"\nVoting Strategy: {result['voting_strategy']}")

    print(f"\n{'=' * 60}")
    print("INDIVIDUAL VOTES:")
    print("=" * 60)
    for v in result["votes"]:
        print(f"\n>>> {v['voter']} ({v['expertise']})")
        print(f"    {v['decision'][:300]}...")

    print(f"\n{'=' * 60}")
    print("AGGREGATED DECISION:")
    print("=" * 60)
    print(result["aggregated_result"])


if __name__ == "__main__":
    main()
