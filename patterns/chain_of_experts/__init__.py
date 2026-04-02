"""Chain-of-Experts Pattern -- Sequential expert processing pipeline.

This pattern passes a task through a chain of specialized expert agents,
each adding their perspective before passing to the next expert.
A final synthesizer combines all expert contributions.
"""

from patterns.chain_of_experts.pattern import ChainOfExpertsPattern

__all__ = ["ChainOfExpertsPattern"]
