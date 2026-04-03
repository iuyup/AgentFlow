"""AgentFlow -- Multi-Agent collaboration design patterns built with LangGraph."""

from patterns.reflection import ReflectionPattern
from patterns.debate import DebatePattern
from patterns.map_reduce import MapReducePattern
from patterns.hierarchical import HierarchicalPattern
from patterns.voting import VotingPattern
from patterns.guardrail import GuardRailPattern
from patterns.rag_agent import RAGAgentPattern
from patterns.human_in_the_loop import HumanInTheLoopPattern
from patterns.chain_of_experts import ChainOfExpertsPattern
from patterns.swarm import SwarmPattern

__all__ = [
    "ReflectionPattern",
    "DebatePattern",
    "MapReducePattern",
    "HierarchicalPattern",
    "VotingPattern",
    "GuardRailPattern",
    "RAGAgentPattern",
    "HumanInTheLoopPattern",
    "ChainOfExpertsPattern",
    "SwarmPattern",
]
