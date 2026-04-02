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


def extract_section(text: str, label: str) -> str:
    """Extract content after a '## Label:' section marker.

    Finds ``## {label}:`` in *text* and returns everything up to the next
    ``## `` section or end-of-string.  Returns an empty string if the
    marker is not found.

    Used by Debate, GuardRail, and RAG-Agent patterns to parse structured
    markdown-style LLM output.
    """
    marker = f"## {label}:"
    idx = text.find(marker)
    if idx == -1:
        return ""
    start = idx + len(marker)
    end = len(text)
    # Known section markers in this codebase
    for m in (
        "## SUMMARY:",
        "## STATUS:",
        "## DECISION:",
        "## Verdict:",
        "## Feedback:",
        "## Decision:",
        "## Reasoning:",
        "## Answer:",
        "## Documents:",
    ):
        if m == marker:
            continue
        pos = text.find(m, start)
        if pos != -1 and pos < end:
            end = pos
    return text[start:end].strip()
