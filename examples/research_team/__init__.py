"""Research Team — Complete application combining Hierarchical + RAG-Agent + GuardRail.

Pipeline:
    Research Question
        --> Hierarchical (Manager decomposes into sub-questions)
        --> RAG-Agent (each Worker retrieves documents for its sub-question)
        --> GuardRail (审核研究结论)
        --> Final research report
"""

from examples.research_team.team import ResearchTeam

__all__ = ["ResearchTeam"]
