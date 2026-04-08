"""Tests for the Self-Improving pattern.

All tests use mocked LLMs -- no API key required.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from langchain_core.messages import AIMessage

from patterns.self_improving.pattern import (
    _parse_json,
    MemoryStore,
    SelfImprovingPattern,
    SelfImprovingState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_llm(*responses: str) -> MagicMock:
    """Return a mock LLM that yields *responses* in order on successive calls."""
    llm = MagicMock()
    llm.invoke = MagicMock(
        side_effect=[AIMessage(content=r) for r in responses]
    )
    return llm


def _make_pattern(mock_llm: MagicMock, storage_dir: Path, **kwargs) -> SelfImprovingPattern:
    return SelfImprovingPattern(
        llm=mock_llm,
        storage_dir=str(storage_dir),
        counter_handler=None,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# _parse_json helper
# ---------------------------------------------------------------------------

class TestParseJson:
    def test_plain_object(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_plain_array(self):
        assert _parse_json('["a", "b"]') == ["a", "b"]

    def test_fenced_block(self):
        text = "Here is the result:\n```json\n{\"score\": 5}\n```\nDone."
        assert _parse_json(text) == {"score": 5}

    def test_fenced_block_no_json_label(self):
        text = "```\n{\"x\": 1}\n```"
        assert _parse_json(text) == {"x": 1}

    def test_prose_around(self):
        text = "The answer is:\nSome explanation.\n{\"steps\": [\"a\", \"b\"], \"result\": \"ok\"}\nThat's it."
        assert _parse_json(text) == {"steps": ["a", "b"], "result": "ok"}

    def test_invalid_json_returns_none(self):
        assert _parse_json("not json at all") is None
        assert _parse_json("") is None
        assert _parse_json(None) is None


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class TestMemoryStore:
    def test_hot_memory_roundtrip(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "mem")
        store.add_memory_entry("Always verify API responses.")
        store.add_memory_entry("Use type hints for public functions.")
        assert "verify API" in store.get_memory_snapshot()
        assert "type hints" in store.get_memory_snapshot()

    def test_hot_memory_limit(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "mem", memory_char_limit=30)
        assert store.add_memory_entry("short") is True
        assert store.add_memory_entry("this is way too long to fit in the limit") is False

    def test_hot_memory_consolidate(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "mem")
        store.add_memory_entry("old entry 1")
        store.add_memory_entry("old entry 2")
        store.consolidate_memory(["new entry A", "new entry B"])
        snap = store.get_memory_snapshot()
        assert "new entry A" in snap
        assert "old entry 1" not in snap

    def test_skill_crud(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "mem")
        skill = {
            "name": "code_review",
            "description": "Review code for bugs",
            "task_type": "code_review",
            "procedure": "Check inputs, outputs, edge cases.",
            "pitfalls": "Missing null checks.",
            "verification": "Run tests.",
            "use_count": 1,
            "avg_score": 8.0,
        }
        store.save_skill(skill)

        # get_skill_index
        index = store.get_skill_index()
        assert len(index) == 1
        assert index[0]["name"] == "code_review"
        assert index[0]["use_count"] == 1
        assert index[0]["avg_score"] == 8.0

        # get_skill (full)
        loaded = store.get_skill("code_review")
        assert loaded is not None
        assert loaded["procedure"] == "Check inputs, outputs, edge cases."

        # update_skill_stats
        store.update_skill_stats("code_review", 9.0)
        reloaded = store.get_skill("code_review")
        assert reloaded["use_count"] == 2
        assert reloaded["avg_score"] == 8.5  # (8 + 9) / 2

        # get_skill not found
        assert store.get_skill("nonexistent") is None

    def test_skill_index_sorted(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "mem")
        store.save_skill({"name": "zebra", "description": "d", "task_type": "a"})
        store.save_skill({"name": "apple", "description": "d", "task_type": "a"})
        index = store.get_skill_index()
        assert [s["name"] for s in index] == ["apple", "zebra"]


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

class TestGraphConstruction:
    def test_build_graph(self, tmp_path: Path):
        llm = _make_mock_llm()
        pattern = _make_pattern(llm, tmp_path / "g")
        graph = pattern.build_graph()
        assert graph is not None


# ---------------------------------------------------------------------------
# Router node
# ---------------------------------------------------------------------------

class TestRouter:
    def test_no_skills_returns_none(self, tmp_path: Path):
        llm = _make_mock_llm('{"task_type": "code_review", "matched_skill": null}')
        pattern = _make_pattern(llm, tmp_path / "r1")

        state: SelfImprovingState = {
            "task": "Review this code",
            "task_type": "",
            "matched_skill": None,
            "execution_steps": [],
            "result": "",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
        }

        result = pattern._router(state)
        assert result["task_type"] == "code_review"
        assert result["matched_skill"] is None

    def test_null_string_returns_none(self, tmp_path: Path):
        llm = _make_mock_llm('{"task_type": "x", "matched_skill": "null"}')
        pattern = _make_pattern(llm, tmp_path / "r2")
        result = pattern._router({"task": "t", "task_type": "", "matched_skill": None, "execution_steps": [], "result": "", "evaluation_score": 0.0, "should_create_skill": False, "should_update_memory": False, "task_count": 0})
        assert result["matched_skill"] is None

    def test_matched_skill_returns_full_dict(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "r3")
        store.save_skill({
            "name": "complexity_analysis",
            "description": "Analyze algorithm complexity",
            "task_type": "analysis",
            "procedure": "Identify loops, recursions, data structures.",
            "pitfalls": "O(n^2) traps.",
            "verification": "Test on large inputs.",
            "use_count": 0,
            "avg_score": 0.0,
        })

        # Use the SAME storage_dir so the router can find the saved skill.
        llm = _make_mock_llm('{"task_type": "analysis", "matched_skill": "complexity_analysis"}')
        pattern = _make_pattern(llm, tmp_path / "r3")  # same path as store above
        result = pattern._router({"task": "t", "task_type": "", "matched_skill": None, "execution_steps": [], "result": "", "evaluation_score": 0.0, "should_create_skill": False, "should_update_memory": False, "task_count": 0})
        assert result["matched_skill"] is not None
        assert result["matched_skill"]["name"] == "complexity_analysis"
        assert "procedure" in result["matched_skill"]


# ---------------------------------------------------------------------------
# Executor node
# ---------------------------------------------------------------------------

class TestExecutor:
    def test_without_skill(self, tmp_path: Path):
        llm = _make_mock_llm('{"steps": ["step1", "step2"], "result": "done"}')
        pattern = _make_pattern(llm, tmp_path / "e1")
        result = pattern._executor({"task": "t", "task_type": "", "matched_skill": None, "execution_steps": [], "result": "", "evaluation_score": 0.0, "should_create_skill": False, "should_update_memory": False, "task_count": 0})
        assert result["execution_steps"] == ["step1", "step2"]
        assert result["result"] == "done"

    def test_with_skill_includes_procedure(self, tmp_path: Path):
        llm = _make_mock_llm('{"steps": ["step1"], "result": "ok"}')
        pattern = _make_pattern(llm, tmp_path / "e2")
        skill = {"name": "test", "description": "d", "task_type": "x", "procedure": "DO_THIS_FIRST", "pitfalls": "N/A", "verification": "N/A", "use_count": 0, "avg_score": 0.0}
        pattern._executor({"task": "t", "task_type": "", "matched_skill": skill, "execution_steps": [], "result": "", "evaluation_score": 0.0, "should_create_skill": False, "should_update_memory": False, "task_count": 0})

        # Check the prompt included the procedure.
        call_args = llm.invoke.call_args
        prompt = call_args[0][0][0].content
        assert "DO_THIS_FIRST" in prompt

    def test_unparseable_response_falls_back(self, tmp_path: Path):
        llm = _make_mock_llm("not json at all")
        pattern = _make_pattern(llm, tmp_path / "e3")
        result = pattern._executor({"task": "t", "task_type": "", "matched_skill": None, "execution_steps": [], "result": "", "evaluation_score": 0.0, "should_create_skill": False, "should_update_memory": False, "task_count": 0})
        assert result["execution_steps"] == ["direct_response"]
        assert result["result"] == "not json at all"


# ---------------------------------------------------------------------------
# Evaluator node
# ---------------------------------------------------------------------------

class TestEvaluator:
    def test_triggers_skill_creation(self, tmp_path: Path):
        llm = _make_mock_llm('{"score": 8.5, "reasoning": "good"}')
        pattern = _make_pattern(llm, tmp_path / "ev1", skill_threshold=7.0, min_steps_for_skill=3)

        state: SelfImprovingState = {
            "task": "t",
            "task_type": "analysis",
            "matched_skill": None,
            "execution_steps": ["a", "b", "c", "d"],  # >= min_steps
            "result": "result",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
        }

        result = pattern._evaluator(state)
        assert result["evaluation_score"] == 8.5
        assert result["should_create_skill"] is True
        assert result["should_update_memory"] is False
        assert result["task_count"] == 1

    def test_skips_skill_if_matched(self, tmp_path: Path):
        llm = _make_mock_llm('{"score": 9.0, "reasoning": "excellent"}')
        pattern = _make_pattern(llm, tmp_path / "ev2", skill_threshold=7.0, min_steps_for_skill=1)
        skill = {"name": "existing", "description": "d", "task_type": "x", "procedure": "p", "pitfalls": "N/A", "verification": "N/A", "use_count": 0, "avg_score": 0.0}

        state: SelfImprovingState = {
            "task": "t",
            "task_type": "x",
            "matched_skill": skill,
            "execution_steps": ["a"],
            "result": "r",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
        }

        result = pattern._evaluator(state)
        assert result["should_create_skill"] is False

    def test_triggers_nudge(self, tmp_path: Path):
        llm = _make_mock_llm('{"score": 5.0, "reasoning": "ok"}')
        pattern = _make_pattern(llm, tmp_path / "ev3", nudge_interval=3)

        state: SelfImprovingState = {
            "task": "t",
            "task_type": "x",
            "matched_skill": None,
            "execution_steps": [],
            "result": "r",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 2,  # next task will be 3 -> 3 % 3 == 0
        }

        result = pattern._evaluator(state)
        assert result["should_update_memory"] is True
        assert result["task_count"] == 3

    def test_updates_skill_stats_on_reuse(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "ev4")
        store.save_skill({"name": "x", "description": "d", "task_type": "x", "procedure": "p", "pitfalls": "N/A", "verification": "N/A", "use_count": 1, "avg_score": 7.0})

        # Use the SAME storage_dir so update_skill_stats finds the skill.
        llm = _make_mock_llm('{"score": 9.0, "reasoning": "g"}')
        pattern = _make_pattern(llm, tmp_path / "ev4")
        skill = store.get_skill("x")

        pattern._evaluator({
            "task": "t",
            "task_type": "x",
            "matched_skill": skill,
            "execution_steps": ["s"],
            "result": "r",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
        })

        reloaded = store.get_skill("x")
        assert reloaded["use_count"] == 2
        assert reloaded["avg_score"] == 8.0


# ---------------------------------------------------------------------------
# Skill extractor node
# ---------------------------------------------------------------------------

class TestSkillExtractor:
    def test_creates_skill_file(self, tmp_path: Path):
        llm = _make_mock_llm(
            '{"name": "bug_review", "description": "Find bugs in python functions", '
            '"task_type": "debugging", "procedure": "1. Identify recursion depth. 2. Check base case.", '
            '"pitfalls": "Infinite recursion.", "verification": "Run with small inputs.", '
            '"use_count": 1, "avg_score": 8.5}'
        )
        pattern = _make_pattern(llm, tmp_path / "se1")

        state: SelfImprovingState = {
            "task": "Review fib bug",
            "task_type": "debugging",
            "matched_skill": None,
            "execution_steps": ["a", "b", "c"],
            "result": "found recursion bug",
            "evaluation_score": 8.5,
            "should_create_skill": True,
            "should_update_memory": False,
            "task_count": 1,
        }

        pattern._skill_extractor(state)

        skill_path = tmp_path / "se1" / "skills" / "bug_review.json"
        assert skill_path.exists()
        with open(skill_path, encoding="utf-8") as f:
            skill = __import__("json").loads(f.read())
        assert skill["name"] == "bug_review"

    def test_skips_when_flag_false(self, tmp_path: Path):
        llm = _make_mock_llm("unexpected call")
        pattern = _make_pattern(llm, tmp_path / "se2")
        pattern._skill_extractor({
            "task": "t",
            "task_type": "x",
            "matched_skill": None,
            "execution_steps": [],
            "result": "r",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
        })
        llm.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# Memory updater node
# ---------------------------------------------------------------------------

class TestMemoryUpdater:
    def test_consolidates_memory(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "mu1")
        store.add_memory_entry("old fact")
        assert "old fact" in store.get_memory_snapshot()

        llm = _make_mock_llm('["fresh lesson 1", "fresh lesson 2"]')
        pattern = _make_pattern(llm, tmp_path / "mu1")

        pattern._memory_updater({
            "task": "t",
            "task_type": "x",
            "matched_skill": None,
            "execution_steps": [],
            "result": "r",
            "evaluation_score": 7.0,
            "should_create_skill": False,
            "should_update_memory": True,
            "task_count": 3,
        })

        snap = store.get_memory_snapshot()
        assert "old fact" not in snap
        assert "fresh lesson 1" in snap

    def test_skips_when_flag_false(self, tmp_path: Path):
        llm = _make_mock_llm("unexpected")
        pattern = _make_pattern(llm, tmp_path / "mu2")
        pattern._memory_updater({
            "task": "t",
            "task_type": "x",
            "matched_skill": None,
            "execution_steps": [],
            "result": "r",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": 0,
        })
        llm.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# Full graph execution
# ---------------------------------------------------------------------------

class TestFullGraph:
    def test_first_task_no_skill(self, tmp_path: Path):
        # Router -> Executor -> Evaluator -> END (score too low to create skill)
        llm = _make_mock_llm(
            '{"task_type": "research", "matched_skill": null}',       # router
            '{"steps": ["look up sources", "synthesize"], "result": "ok"}',  # executor
            '{"score": 5.0, "reasoning": "ok"}',                       # evaluator
        )
        pattern = _make_pattern(llm, tmp_path / "fg1", nudge_interval=5)

        result = pattern.run("Research quicksort", task_count=0)

        assert result["task_type"] == "research"
        assert result["matched_skill"] is None
        assert result["evaluation_score"] == 5.0
        assert result["should_create_skill"] is False
        assert result["task_count"] == 1

    def test_creates_skill_on_high_score(self, tmp_path: Path):
        # Router -> Executor -> Evaluator -> SkillExtractor -> END
        llm = _make_mock_llm(
            '{"task_type": "analysis", "matched_skill": null}',                # router
            '{"steps": ["step1", "step2", "step3"], "result": "analysis done"}',  # executor
            '{"score": 8.5, "reasoning": "good"}',                              # evaluator
            '{"name": "complexity_analysis", "description": "Analyze algo complexity", "task_type": "analysis", "procedure": "Identify loops.", "pitfalls": "Watch for O(n^2).", "verification": "Test large n.", "use_count": 1, "avg_score": 8.5}',  # skill extractor
        )
        pattern = _make_pattern(llm, tmp_path / "fg2", skill_threshold=7.0, min_steps_for_skill=3, nudge_interval=10)

        result = pattern.run("Analyze quicksort complexity", task_count=0)

        assert result["should_create_skill"] is True
        assert result["evaluation_score"] == 8.5

        skill_path = tmp_path / "fg2" / "skills" / "complexity_analysis.json"
        assert skill_path.exists()

    def test_reuses_skill_on_second_task(self, tmp_path: Path):
        store = MemoryStore(tmp_path / "fg3")

        # Pre-populate a skill so the second run finds it.
        store.save_skill({
            "name": "algo_complexity",
            "description": "Analyze algorithm time/space complexity",
            "task_type": "analysis",
            "procedure": "Identify loops and recursion depth.",
            "pitfalls": "O(n^2) degradation in quicksort.",
            "verification": "Test with large inputs.",
            "use_count": 1,
            "avg_score": 8.5,
        })

        # Second run: router finds the skill.
        llm = _make_mock_llm(
            '{"task_type": "analysis", "matched_skill": "algo_complexity"}',  # router: skill matched
            '{"steps": ["step1"], "result": "result"}',                      # executor
            '{"score": 9.0, "reasoning": "g"}',                              # evaluator
        )
        pattern = _make_pattern(llm, tmp_path / "fg3", nudge_interval=10)

        result = pattern.run("Analyze merge sort complexity", task_count=1)

        assert result["matched_skill"] is not None
        assert result["matched_skill"]["name"] == "algo_complexity"
        assert result["evaluation_score"] == 9.0

        # Skill use_count should be updated.
        reloaded = store.get_skill("algo_complexity")
        assert reloaded["use_count"] == 2

    def test_nudge_on_interval(self, tmp_path: Path):
        # task_count 2 -> next is 3, 3 % 3 == 0 -> nudge fires
        llm = _make_mock_llm(
            '{"task_type": "x", "matched_skill": null}',
            '{"steps": ["s"], "result": "r"}',
            '{"score": 6.0, "reasoning": "ok"}',
            '["consolidated entry"]',
        )
        pattern = _make_pattern(llm, tmp_path / "fg4", nudge_interval=3)
        store = MemoryStore(tmp_path / "fg4")
        store.add_memory_entry("old entry")

        result = pattern.run("task", task_count=2)

        assert result["should_update_memory"] is True
        assert "old entry" not in store.get_memory_snapshot()
