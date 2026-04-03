"""Shared utilities used across all AgentFlow patterns."""

import os
import re


def get_default_llm(model: str | None = None):
    """Auto-detect LLM provider: DeepSeek > OpenAI.

    Checks for ``DEEPSEEK_API_KEY`` first, then falls back to OpenAI.
    """
    if os.getenv("DEEPSEEK_API_KEY"):
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(model=model or "deepseek-chat")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model or "gpt-4o-mini")


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
