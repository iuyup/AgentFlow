"""AI Newsroom — Complete application combining MapReduce + Debate + Reflection.

This application demonstrates how to compose multiple AgentFlow patterns
into a complete news production pipeline.

Pipeline:
    Topic Input
        --> MapReduce (multi-source news collection)
        --> Debate (pro/con analysis)
        --> Reflection (editorial polish)
        --> Final news article
"""

from examples.ai_newsroom.newsroom import AINewsroom

__all__ = ["AINewsroom"]
