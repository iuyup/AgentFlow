"""MapReduce Pattern Example -- Multi-Source News Analysis.

Demonstrates parallel fan-out analysis of multiple news sources on a single
topic, followed by a synthesis step that merges all findings.

Usage:
    1. Copy ``.env.example`` to ``.env`` and add your OpenAI API key.
    2. Run::

        python -m patterns.map_reduce.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.map_reduce.pattern import MapReducePattern


def main() -> None:
    sources = [
        "TechCrunch: Report on latest AI funding rounds and startup valuations",
        "Reuters: Analysis of global semiconductor supply chain disruptions",
        "MIT Technology Review: Breakthroughs in large language model efficiency",
        "Bloomberg: Wall Street's adoption of AI trading algorithms",
    ]

    pattern = MapReducePattern()
    result = pattern.run(
        topic="Current State of the AI Industry in 2024",
        sources=sources,
    )

    # -- Pretty-print results -----------------------------------------------
    print("=" * 60)
    print("MAPREDUCE PATTERN -- Multi-Source News Analysis")
    print("=" * 60)
    print(f"\nTopic: {result['topic']}")
    print(f"Sources Analyzed: {len(result['sources'])}")

    print(f"\n{'=' * 60}")
    print("INDIVIDUAL ANALYSES:")
    print("=" * 60)
    for r in result["results"]:
        print(f"\n>>> {r['source']}")
        print(f"    {r['analysis'][:200]}...")

    print(f"\n{'=' * 60}")
    print("FINAL SYNTHESIS:")
    print("=" * 60)
    print(result["final_summary"])


if __name__ == "__main__":
    main()
