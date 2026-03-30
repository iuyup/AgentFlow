"""Debate Pattern Example — Investment Decision: Bull vs Bear.

Two investors debate whether to invest $1M in an AI startup.
A neutral moderator synthesizes the arguments and reaches a decision.

Usage:
    python -m patterns.debate.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.debate.pattern import DebatePattern


def main() -> None:
    debaters = [
        {
            "name": "Bull",
            "role": "Optimistic investor",
            "system_prompt": (
                "You are Bull, a seasoned technology investor who has backed "
                "three unicorns in the last decade. You have a deep conviction "
                "that large language models will reshape every industry within "
                "five years. You evaluate startups on team quality, TAM "
                "(total addressable market), technological moat, and speed of "
                "execution. You believe early-stage AI companies at $50M "
                "valuations are bargains compared to where the market is "
                "heading. You cite precedents like early investments in "
                "OpenAI, DeepMind, and Anthropic. You acknowledge risks but "
                "frame them as manageable through portfolio diversification "
                "and active board involvement."
            ),
        },
        {
            "name": "Bear",
            "role": "Cautious risk analyst",
            "system_prompt": (
                "You are Bear, a veteran risk analyst with 20 years of "
                "experience surviving dot-com, crypto, and clean-tech "
                "bubbles. You have seen countless startups fail despite "
                "strong technology because of poor unit economics, "
                "competition from incumbents, and regulatory headwinds. You "
                "focus on cash burn rates, customer acquisition costs, "
                "revenue multiples, and defensibility. You believe the "
                "current AI market is overheated — most startups at $50M "
                "valuations have minimal revenue, thin margins due to API "
                "costs, and no real moat against big tech. You advocate for "
                "waiting for market correction or investing in established "
                "companies with proven AI revenue streams instead."
            ),
        },
    ]

    pattern = DebatePattern(max_rounds=3)
    result = pattern.run(
        topic="Should we invest $1M in an AI startup at a $50M valuation?",
        debaters=debaters,
    )

    # ── Pretty-print the debate ──────────────────────────────────────
    print("=" * 60)
    print("DEBATE PATTERN — Investment Decision")
    print("=" * 60)

    # Group arguments by round
    rounds: dict[int, list[dict]] = {}
    for entry in result["debate_history"]:
        r = entry.get("round", 0)
        rounds.setdefault(r, []).append(entry)

    for round_num in sorted(rounds):
        print(f"\n{'─' * 60}")
        print(f"  ROUND {round_num + 1}")
        print(f"{'─' * 60}")
        for entry in rounds[round_num]:
            print(f"\n  [{entry['name']}  —  {entry['role']}]")
            print(f"  {'.' * 40}")
            # Indent the argument text
            for line in entry["argument"].split("\n"):
                print(f"    {line}")

    # Moderator summary & decision
    print(f"\n{'=' * 60}")
    print("  MODERATOR SUMMARY")
    print(f"{'=' * 60}")
    print(f"\n  {result.get('moderator_summary', 'N/A')}")

    if result.get("final_decision"):
        print(f"\n{'=' * 60}")
        print("  FINAL DECISION")
        print(f"{'=' * 60}")
        print(f"\n  {result['final_decision']}")

    print(f"\n{'=' * 60}")
    print(f"  Debate concluded after {result['current_round']} round(s)")
    print(f"  Settled by consensus: {result.get('is_settled', False)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
