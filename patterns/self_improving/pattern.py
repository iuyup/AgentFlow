"""Self-Improving Pattern -- Persistent skills + cross-task learning.

Inspired by the Hermes Agent's layered-memory architecture, this pattern
gives an agent two complementary memories:

1. **Hot memory** -- a small, always-loaded snapshot injected into every
   system prompt (environment facts, conventions, lessons learned).
2. **Skill store** -- a cold, on-demand library of reusable *procedures*
   extracted from successful task completions.  Only the skill *index*
   (name + one-line description) is loaded by default; full content is
   fetched only when the router matches a skill to the current task.

Every task flows through five nodes:

    router -> executor -> evaluator -> [skill_extractor?] -> [memory_updater?] -> END

- ``router`` classifies the task and checks the skill index for a match.
- ``executor`` performs the task, optionally guided by the matched skill.
- ``evaluator`` scores the result (1-10) and decides whether the run was
  good enough to extract a new skill, and whether the periodic memory
  consolidation nudge should fire.
- ``skill_extractor`` writes a structured skill JSON when the run was
  high-quality and not already covered by an existing skill.
- ``memory_updater`` consolidates the hot memory every N tasks so it stays
  bounded in size.

This is the only AgentFlow pattern that *learns across runs*: state
persists in ``storage_dir`` between invocations, so the agent gets
better the more you use it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TypedDict

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from agentflow.utils import get_default_llm as _default_llm
from agentflow.utils import get_llm_call_count


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class SelfImprovingState(TypedDict):
    """State that flows through the self-improving agent graph."""

    task: str
    task_type: str
    matched_skill: Optional[dict]
    execution_steps: list[str]
    result: str
    evaluation_score: float
    should_create_skill: bool
    should_update_memory: bool
    task_count: int


# ---------------------------------------------------------------------------
# JSON parsing helper (robust against ```json fences and surrounding prose)
# ---------------------------------------------------------------------------


def _parse_json(text: str) -> Optional[object]:
    """Extract and parse the first JSON object or array from *text*.

    LLMs often wrap JSON in markdown fences (```json ... ```) or sandwich
    it between explanatory prose.  We greedily match the first ``{...}``
    or ``[...]`` block via regex and try to parse it.  Returns ``None`` on
    failure so callers can fall back gracefully.
    """
    if not text:
        return None

    # Try fenced block first.
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text

    # Greedy: prefer the largest object/array, then fall back to the first.
    for pattern in (r"\{.*\}", r"\[.*\]"):
        match = re.search(pattern, candidate, re.DOTALL)
        if not match:
            continue
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# MemoryStore -- two-layer persistent memory
# ---------------------------------------------------------------------------


class MemoryStore:
    """Two-layer persistent memory inspired by the Hermes Agent.

    Layer 1 -- *hot memory* (``MEMORY.json``):
        Always injected into the system prompt.  Capped at
        ``memory_char_limit`` characters (~800 tokens) to keep prompt
        overhead bounded.  Holds environment facts, conventions, and
        lessons learned.

    Layer 2 -- *skill store* (``skills/*.json``):
        Cold storage with progressive disclosure.  ``get_skill_index``
        returns only names + descriptions; ``get_skill`` loads the full
        procedure on demand when the router matches.
    """

    DEFAULT_MEMORY_CHAR_LIMIT = 2000

    def __init__(
        self,
        storage_dir: str | Path = "./.agent_memory",
        memory_char_limit: int = DEFAULT_MEMORY_CHAR_LIMIT,
    ):
        self.storage_dir = Path(storage_dir)
        self.memory_file = self.storage_dir / "MEMORY.json"
        self.skills_dir = self.storage_dir / "skills"
        self.memory_char_limit = memory_char_limit

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self._save_memory({"entries": [], "updated_at": None})

    # -- hot memory layer --------------------------------------------------

    def get_memory_snapshot(self) -> str:
        """Return the hot-memory entries as a bullet list for prompt injection."""
        data = self._load_memory()
        if not data["entries"]:
            return "[No persistent memory yet]"
        return "\n".join(f"- {e}" for e in data["entries"])

    def add_memory_entry(self, entry: str) -> bool:
        """Append an entry to hot memory.

        Returns ``False`` if the addition would exceed ``memory_char_limit``,
        signalling that the caller should consolidate first.
        """
        data = self._load_memory()
        current_text = "\n".join(data["entries"])
        if len(current_text) + len(entry) + 2 > self.memory_char_limit:
            return False
        data["entries"].append(entry)
        data["updated_at"] = datetime.now().isoformat()
        self._save_memory(data)
        return True

    def consolidate_memory(self, consolidated_entries: list[str]) -> None:
        """Replace all hot memory with a consolidated set of entries."""
        self._save_memory(
            {
                "entries": consolidated_entries,
                "updated_at": datetime.now().isoformat(),
            }
        )

    def _load_memory(self) -> dict:
        return json.loads(self.memory_file.read_text(encoding="utf-8"))

    def _save_memory(self, data: dict) -> None:
        self.memory_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # -- skill store layer -------------------------------------------------

    def get_skill_index(self) -> list[dict]:
        """Return the lightweight skill index (name + description only).

        This is the *progressive disclosure* layer -- always cheap to load.
        Sorted by name for reproducible test output.
        """
        index = []
        for f in sorted(self.skills_dir.glob("*.json")):
            skill = json.loads(f.read_text(encoding="utf-8"))
            index.append(
                {
                    "name": skill["name"],
                    "description": skill["description"],
                    "task_type": skill.get("task_type", ""),
                    "use_count": skill.get("use_count", 0),
                    "avg_score": skill.get("avg_score", 0),
                }
            )
        return index

    def get_skill(self, skill_name: str) -> Optional[dict]:
        """Load the full skill document. Returns ``None`` if not found."""
        path = self.skills_dir / f"{skill_name}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def save_skill(self, skill: dict) -> None:
        """Persist a new or updated skill to disk."""
        skill["updated_at"] = datetime.now().isoformat()
        path = self.skills_dir / f"{skill['name']}.json"
        path.write_text(
            json.dumps(skill, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update_skill_stats(self, skill_name: str, score: float) -> None:
        """Update a skill's running average score and use counter."""
        skill = self.get_skill(skill_name)
        if skill is None:
            return
        skill["use_count"] = skill.get("use_count", 0) + 1
        prior_total = skill.get("avg_score", 0) * (skill["use_count"] - 1)
        skill["avg_score"] = round((prior_total + score) / skill["use_count"], 2)
        self.save_skill(skill)


# ---------------------------------------------------------------------------
# Pattern implementation
# ---------------------------------------------------------------------------


class SelfImprovingPattern:
    """A LangGraph agent that builds reusable skills as it runs.

    Parameters
    ----------
    model : str | None
        Model name forwarded to :func:`agentflow.utils.get_default_llm`
        when *llm* is not supplied.
    llm : BaseChatModel | None
        Pre-configured LangChain chat model. Takes precedence over *model*.
    storage_dir : str
        Directory where ``MEMORY.json`` and ``skills/*.json`` live.
        Persists between runs -- this is what makes the agent "improve".
    nudge_interval : int
        Trigger memory consolidation every N completed tasks. Hermes uses
        15; we default to 5 for faster feedback in demos.
    skill_threshold : float
        Minimum evaluator score (out of 10) required to extract a new skill.
    min_steps_for_skill : int
        Skip skill extraction unless the executor recorded at least this
        many steps -- single-step tasks rarely contain reusable procedures.
    counter_handler : BaseCallbackHandler | None
        Optional LangChain callback for counting LLM invocations.
    """

    def __init__(
        self,
        model: str | None = None,
        llm: BaseChatModel | None = None,
        storage_dir: str = "./.agent_memory",
        nudge_interval: int = 5,
        skill_threshold: float = 7.0,
        min_steps_for_skill: int = 3,
        counter_handler: BaseCallbackHandler | None = None,
    ):
        self.llm = llm or _default_llm(model, counter_handler)
        self.store = MemoryStore(storage_dir)
        self.nudge_interval = nudge_interval
        self.skill_threshold = skill_threshold
        self.min_steps_for_skill = min_steps_for_skill
        self.counter_handler = counter_handler

    # ------------------------------------------------------------------
    # Node 1: Router -- classify task and look up skills
    # ------------------------------------------------------------------

    def _router(self, state: SelfImprovingState) -> dict:
        skill_index = self.store.get_skill_index()
        if skill_index:
            skill_list = "\n".join(
                f"  - {s['name']}: {s['description']} "
                f"(used {s['use_count']}x, avg_score={s['avg_score']})"
                for s in skill_index
            )
        else:
            skill_list = "  [No skills yet]"

        memory_snapshot = self.store.get_memory_snapshot()

        prompt = (
            "You are a task router. Analyze the user's task and:\n"
            "1. Classify the task_type (e.g. code_review, data_analysis, "
            "writing, research, debugging).\n"
            "2. Check if any existing skill matches. If so, return its name.\n\n"
            f"Available skills:\n{skill_list}\n\n"
            f"Persistent memory:\n{memory_snapshot}\n\n"
            f"User task: {state['task']}\n\n"
            "Respond ONLY in JSON:\n"
            '{"task_type": "...", "matched_skill": "skill_name_or_null"}'
        )

        response = self.llm.invoke([SystemMessage(content=prompt)])
        parsed = _parse_json(response.content) or {}

        task_type = parsed.get("task_type", "general") if isinstance(parsed, dict) else "general"
        matched_name = parsed.get("matched_skill") if isinstance(parsed, dict) else None

        # LLMs sometimes return the literal string "null" or "None".
        if isinstance(matched_name, str) and matched_name.strip().lower() in ("null", "none", ""):
            matched_name = None

        matched: Optional[dict] = None
        if matched_name:
            matched = self.store.get_skill(matched_name)

        return {"task_type": task_type, "matched_skill": matched}

    # ------------------------------------------------------------------
    # Node 2: Executor -- perform the task, optionally guided by a skill
    # ------------------------------------------------------------------

    def _executor(self, state: SelfImprovingState) -> dict:
        skill_guidance = ""
        if state.get("matched_skill"):
            skill = state["matched_skill"]
            skill_guidance = (
                "\nYou have a relevant skill to guide you:\n"
                f"Skill: {skill['name']}\n"
                f"Procedure: {skill.get('procedure', 'N/A')}\n"
                f"Pitfalls to avoid: {skill.get('pitfalls', 'N/A')}\n"
                f"Verification: {skill.get('verification', 'N/A')}\n"
            )

        memory_snapshot = self.store.get_memory_snapshot()

        prompt = (
            "You are a capable AI assistant. Complete the following task.\n"
            "Think step by step. Record each major step you take.\n\n"
            f"Persistent memory context:\n{memory_snapshot}\n"
            f"{skill_guidance}\n"
            f"Task: {state['task']}\n\n"
            "Respond ONLY in JSON:\n"
            '{"steps": ["step1", "step2", ...], "result": "final result"}'
        )

        response = self.llm.invoke([SystemMessage(content=prompt)])
        parsed = _parse_json(response.content)

        if isinstance(parsed, dict):
            steps = parsed.get("steps", ["direct_response"])
            result = parsed.get("result", response.content)
        else:
            steps = ["direct_response"]
            result = response.content

        return {"execution_steps": steps, "result": result}

    # ------------------------------------------------------------------
    # Node 3: Evaluator -- score the run, decide what to extract
    # ------------------------------------------------------------------

    def _evaluator(self, state: SelfImprovingState) -> dict:
        prompt = (
            "Evaluate the quality of this task execution.\n\n"
            f"Task: {state['task']}\n"
            f"Steps taken: {json.dumps(state['execution_steps'], ensure_ascii=False)}\n"
            f"Result: {state['result']}\n\n"
            "Score 1-10 on correctness, completeness, efficiency.\n"
            'Respond ONLY in JSON: {"score": N, "reasoning": "..."}'
        )

        response = self.llm.invoke([SystemMessage(content=prompt)])
        parsed = _parse_json(response.content)

        try:
            score = float(parsed["score"]) if isinstance(parsed, dict) else 5.0
        except (KeyError, TypeError, ValueError):
            score = 5.0

        task_count = state.get("task_count", 0) + 1
        num_steps = len(state.get("execution_steps", []))

        should_create = (
            score >= self.skill_threshold
            and num_steps >= self.min_steps_for_skill
            and not state.get("matched_skill")
        )

        # When the agent reused an existing skill, update its running stats.
        if state.get("matched_skill"):
            self.store.update_skill_stats(state["matched_skill"]["name"], score)

        return {
            "evaluation_score": score,
            "should_create_skill": should_create,
            "should_update_memory": (task_count % self.nudge_interval == 0),
            "task_count": task_count,
        }

    # ------------------------------------------------------------------
    # Node 4: Skill extractor -- distil a successful run into a skill
    # ------------------------------------------------------------------

    def _skill_extractor(self, state: SelfImprovingState) -> dict:
        if not state.get("should_create_skill"):
            return {}

        prompt = (
            "You completed a task successfully. Extract a reusable skill "
            "document.\n\n"
            f"Task type: {state['task_type']}\n"
            f"Task: {state['task']}\n"
            f"Steps: {json.dumps(state['execution_steps'], ensure_ascii=False)}\n"
            f"Result: {state['result']}\n"
            f"Score: {state['evaluation_score']}\n\n"
            "Create a skill in JSON format:\n"
            "{\n"
            '  "name": "short_snake_case_name",\n'
            '  "description": "One-line description of when to use this skill",\n'
            f'  "task_type": "{state["task_type"]}",\n'
            '  "procedure": "Step-by-step procedure that worked",\n'
            '  "pitfalls": "Common mistakes to avoid",\n'
            '  "verification": "How to verify the result is correct",\n'
            '  "use_count": 1,\n'
            f'  "avg_score": {state["evaluation_score"]}\n'
            "}"
        )

        response = self.llm.invoke([SystemMessage(content=prompt)])
        skill = _parse_json(response.content)

        if isinstance(skill, dict) and "name" in skill:
            self.store.save_skill(skill)
            print(f"  [skill] new skill saved: {skill['name']}")
        else:
            print("  [skill] failed to parse skill JSON, skipping")

        return {}

    # ------------------------------------------------------------------
    # Node 5: Memory updater -- periodic consolidation nudge
    # ------------------------------------------------------------------

    def _memory_updater(self, state: SelfImprovingState) -> dict:
        if not state.get("should_update_memory"):
            return {}

        current_memory = self.store.get_memory_snapshot()

        prompt = (
            "You are a memory manager. Review and consolidate the agent's "
            "persistent memory.\n\n"
            f"Current memory:\n{current_memory}\n\n"
            f"Recent task: {state['task']}\n"
            f"Recent result quality: {state['evaluation_score']}/10\n"
            f"Task type: {state['task_type']}\n\n"
            "Rules:\n"
            f"- Keep total under {self.store.memory_char_limit} characters\n"
            "- Merge duplicate entries\n"
            "- Remove stale or outdated entries\n"
            "- Add any new durable lessons from the recent task\n"
            "- Focus on *actionable* knowledge, not raw facts\n\n"
            'Respond ONLY in JSON: ["entry1", "entry2", ...]'
        )

        response = self.llm.invoke([SystemMessage(content=prompt)])
        entries = _parse_json(response.content)

        if isinstance(entries, list):
            self.store.consolidate_memory([str(e) for e in entries])
            print(f"  [memory] consolidated into {len(entries)} entries")

        return {}

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _after_evaluator(self, state: SelfImprovingState) -> str:
        if state.get("should_create_skill"):
            return "skill_extractor"
        if state.get("should_update_memory"):
            return "memory_updater"
        return "end"

    def _after_skill_extractor(self, state: SelfImprovingState) -> str:
        if state.get("should_update_memory"):
            return "memory_updater"
        return "end"

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def build_graph(self) -> StateGraph:
        """Construct and compile the self-improving agent graph."""
        graph = StateGraph(SelfImprovingState)

        graph.add_node("router", self._router)
        graph.add_node("executor", self._executor)
        graph.add_node("evaluator", self._evaluator)
        graph.add_node("skill_extractor", self._skill_extractor)
        graph.add_node("memory_updater", self._memory_updater)

        graph.add_edge(START, "router")
        graph.add_edge("router", "executor")
        graph.add_edge("executor", "evaluator")
        graph.add_conditional_edges(
            "evaluator",
            self._after_evaluator,
            {
                "skill_extractor": "skill_extractor",
                "memory_updater": "memory_updater",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "skill_extractor",
            self._after_skill_extractor,
            {
                "memory_updater": "memory_updater",
                "end": END,
            },
        )
        graph.add_edge("memory_updater", END)

        return graph.compile()

    # ------------------------------------------------------------------
    # Public runner
    # ------------------------------------------------------------------

    def run(self, task: str, task_count: int = 0) -> dict:
        """Execute a single task end-to-end and return the final state.

        Parameters
        ----------
        task : str
            Natural-language task description.
        task_count : int
            Running counter of completed tasks across this session. Used
            to trigger the periodic memory-consolidation nudge. Persist
            this value yourself between calls if you want continuity.

        Returns
        -------
        dict
            Final :class:`SelfImprovingState` augmented with
            ``llm_call_count``.
        """
        graph = self.build_graph()
        initial_state: SelfImprovingState = {
            "task": task,
            "task_type": "",
            "matched_skill": None,
            "execution_steps": [],
            "result": "",
            "evaluation_score": 0.0,
            "should_create_skill": False,
            "should_update_memory": False,
            "task_count": task_count,
        }
        result = graph.invoke(initial_state)
        result["llm_call_count"] = get_llm_call_count(self.counter_handler)
        return result
