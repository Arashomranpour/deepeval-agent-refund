"""Shrink agent traces before DeepEval sends them to the judge.

Groq's free tier caps a single request at ~8k tokens. A raw LangGraph trace of this
agent is ~10k tokens, because every LLM span repeats the full system prompt and tool
schemas and every graph-node span repeats the whole message history. The trace-based
metrics (Task Completion, Step Efficiency, Plan Quality, Plan Adherence) then fail
with HTTP 413.

This keeps what the judge needs - the user's input, every tool call with its inputs
and outputs, each LLM decision, and the final answer - and drops the repetition.
Call `install()` once before running the evaluation.
"""

from typing import Any

from deepeval.tracing.tracing import trace_manager

MAX_STR = 600  # characters kept from any single long value


def _short(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_STR:
        return value[:MAX_STR] + " …[truncated]"
    if isinstance(value, dict):
        return {k: _short(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_short(v) for v in value]
    return value


def _slim(span: Any, is_root: bool = False) -> Any:
    if not isinstance(span, dict):
        return span
    span = dict(span)
    if span.get("type") == "llm":
        # Prompt = system prompt + tool schemas + history, repeated on every call.
        span.pop("input", None)
        for key in ("integration", "provider", "input_token_count", "output_token_count"):
            span.pop(key, None)
    elif span.get("name") == "model":
        # LangGraph "model" node: its input/output duplicate the message history;
        # the LLM decision itself is kept on the child llm span.
        span.pop("input", None)
        span.pop("output", None)
    if is_root and isinstance(span.get("output"), dict):
        # The root output repeats every message; the final answer is enough.
        messages = span["output"].get("messages")
        if messages:
            span["output"] = {"final_answer": messages[-1]}
    span.pop("integration", None)
    span["children"] = [_slim(c) for c in span.get("children") or []]
    return _short(span)


def install() -> None:
    """Patch DeepEval's trace builder so every metric receives the slim trace."""
    if getattr(trace_manager, "_slim_trace_installed", False):
        return
    original = trace_manager.create_nested_spans_dict

    def slim_nested_spans_dict(*args, **kwargs):
        return _slim(original(*args, **kwargs), is_root=True)

    trace_manager.create_nested_spans_dict = slim_nested_spans_dict
    trace_manager._slim_trace_installed = True
