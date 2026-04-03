"""Shared utilities used across all AgentFlow patterns."""

import os
import re

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel


# ---------------------------------------------------------------------------
# LLM call counter
# ---------------------------------------------------------------------------


class LLMCallCounterHandler(BaseCallbackHandler):
    """LangChain callback handler that counts LLM invocations (sync + async).

    Tracks the total number of ``on_chat_model_start`` events across a run.
    Uses an internal counter list so increments are visible across async
    task boundaries (unlike ``ContextVar`` whose set() is local to each copy).

    Usage::

        from agentflow.utils import get_default_llm, reset_llm_count, get_llm_call_count

        handler = LLMCallCounterHandler()
        reset_llm_count(handler)
        llm = get_default_llm(counter_handler=handler)
        llm.invoke([...])           # counted
        llm.ainvoke([...])          # counted
        print(get_llm_call_count(handler))  # 2
    """

    def __init__(self) -> None:
        self._count: list[int] = [0]

    def on_chat_model_start(
        self,
        serialized,
        messages,
        **kwargs,
    ) -> None:
        self._count[0] += 1

    def on_llm_start(
        self,
        serialized,
        prompts,
        **kwargs,
    ) -> None:
        self._count[0] += 1


def reset_llm_count(handler: LLMCallCounterHandler | None = None) -> None:
    """Reset the LLM call counter to zero.

    When called with the handler instance, resets that specific counter.
    When called without arguments, resets all handlers created by the module
    (legacy compatibility).
    """
    if handler is not None:
        handler._count[0] = 0
    else:
        # Legacy: reset all known handlers (no-op in new code path;
        # kept for backward compatibility)
        pass


def get_llm_call_count(handler: LLMCallCounterHandler | None = None) -> int:
    """Return the current LLM call count for the given handler."""
    if handler is not None:
        return handler._count[0]
    return 0


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------


def get_default_llm(
    model: str | None = None,
    counter_handler: BaseCallbackHandler | None = None,
) -> BaseChatModel:
    """Auto-detect LLM provider: DeepSeek > OpenAI.

    Checks for ``DEEPSEEK_API_KEY`` first, then falls back to OpenAI.

    Args:
        model: Override the default model name.
        counter_handler: Optional LangChain callback handler to attach to the
            LLM. When provided, every ``invoke`` / ``ainvoke`` call on the
            returned LLM will be counted via ``get_llm_call_count()``.
    """
    if os.getenv("DEEPSEEK_API_KEY"):
        from langchain_deepseek import ChatDeepSeek

        llm = ChatDeepSeek(model=model or "deepseek-chat")
    else:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model or "gpt-4o-mini")

    if counter_handler is not None:
        llm = llm.with_config(callbacks=[counter_handler])

    return llm


# ---------------------------------------------------------------------------
# Output extraction helpers
# ---------------------------------------------------------------------------


def extract_section(
    text: str,
    label: str,
    *,
    prefix: str = "## ",
    known_markers: tuple[str, ...] | None = None,
) -> str:
    """Extract content after a ``{prefix}{label}:`` section marker.

    Finds ``{prefix}{label}:`` in *text* and returns everything up to the next
    known marker or end-of-string.  Returns an empty string if the marker is
    not found.

    Args:
        text: The text to search.
        label: The label to find (e.g. ``"SUMMARY"``).
        prefix: Prefix before each label marker. Defaults to ``"## "`` for
            markdown-style ``## SUMMARY:`` output. Pass ``""`` for plain
            ``SUMMARY:`` output.
        known_markers: Override the list of known next markers. Defaults to
            the standard set used across AgentFlow patterns.
    """
    marker = f"{prefix}{label}:"
    idx = text.find(marker)
    if idx == -1:
        return ""
    start = idx + len(marker)
    end = len(text)

    if known_markers is None:
        known_markers = (
            "## SUMMARY:",
            "## STATUS:",
            "## DECISION:",
            "## Verdict:",
            "## Feedback:",
            "## Decision:",
            "## Reasoning:",
            "## Answer:",
            "## Documents:",
        )

    for m in known_markers:
        if m == marker:
            continue
        pos = text.find(m, start)
        if pos != -1 and pos < end:
            end = pos
    return text[start:end].strip()
