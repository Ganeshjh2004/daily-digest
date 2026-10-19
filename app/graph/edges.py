"""Conditional edge functions for the Daily Digest graph."""


def after_select(state: dict) -> str:
    """Skip summarization when no selected article needs work."""
    return "save_output" if not state["selected"] else "summarize"


def after_validate(state: dict) -> str:
    """Retry failed pairs once before continuing to persistence."""
    has_failures = any(summary["status"] == "failed" for summary in state["summaries"])
    return "retry" if has_failures and state["retry_count"] < 1 else "save_output"
