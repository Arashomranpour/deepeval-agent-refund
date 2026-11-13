"""Offline unit tests for the agent tools, streaming, trace slimming and results."""

from types import SimpleNamespace

import results
from agent import stream_reply
from slim_trace import _slim
from tools import STORE_TODAY, calculate_right_refund, get_today_date, get_user_purchase_history


# --- tools ----------------------------------------------------------------------
def test_store_date_is_fixed():
    assert get_today_date.invoke({}) == STORE_TODAY == "2026-10-16"


def test_refund_quote_says_no_ticket_yet():
    out = calculate_right_refund.invoke({"user": "user123", "items": [{"name": "book"}, {"name": "pen"}]})
    assert "Quoted refund amount: 30" in out
    assert "issue_refund_ticket" in out


def test_unknown_user_has_no_history():
    assert get_user_purchase_history.invoke({"user": "user999"}) == {"status": "there was no username found"}


# --- streaming -------------------------------------------------------------------
class FakeAgent:
    """Replays LangGraph stream events: (mode, data) pairs."""

    def __init__(self, events):
        self.events = events

    def stream(self, *_args, **_kwargs):
        yield from self.events


def ai(content="", tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def test_stream_reply_maps_tools_and_tokens():
    call = {"id": "c1", "name": "get_user_purchase_history", "args": {"user": "user123"}}
    events = [
        ("messages", (ai("Let me check"), {"langgraph_node": "model"})),
        ("updates", {"model": {"messages": [ai(tool_calls=[call])]}}),
        ("updates", {"tools": {"messages": [SimpleNamespace(tool_call_id="c1", content="{...}")]}}),
        ("messages", (ai("Refunded "), {"langgraph_node": "model"})),
        ("messages", (ai("$30."), {"langgraph_node": "model"})),
        ("messages", (ai("tool output"), {"langgraph_node": "tools"})),  # not answer text
    ]
    out = list(stream_reply(FakeAgent(events), "hi", {}))
    assert out == [
        ("token", "Let me check"),
        ("reset", None),
        ("tool_call", {"id": "c1", "name": "get_user_purchase_history", "args": {"user": "user123"}}),
        ("tool_result", {"id": "c1", "output": "{...}"}),
        ("token", "Refunded "),
        ("token", "$30."),
    ]


# --- trace slimming -----------------------------------------------------------------
def test_slim_trace_drops_repeated_prompts_keeps_tools():
    trace = {
        "type": "agent", "name": "LangGraph", "integration": "langchain",
        "input": {"messages": [{"role": "user", "content": "refund the book"}]},
        "output": {"messages": ["m1", "m2", "final answer"]},
        "children": [
            {"type": "base", "name": "model", "input": "history" * 100, "output": "history",
             "children": [{"type": "llm", "name": "ChatGroq", "input": "SYSTEM PROMPT" * 500,
                           "output": "calls tool", "input_token_count": 900}]},
            {"type": "tool", "name": "get_today_date", "input": {}, "output": "2026-10-16"},
        ],
    }
    slim = _slim(trace, is_root=True)
    assert slim["output"] == {"final_answer": "final answer"}
    model, tool = slim["children"]
    assert "input" not in model and "output" not in model
    assert "input" not in model["children"][0] and "input_token_count" not in model["children"][0]
    assert model["children"][0]["output"] == "calls tool"
    assert tool["output"] == "2026-10-16"
    assert "integration" not in slim


def test_slim_trace_truncates_long_values():
    slim = _slim({"type": "tool", "name": "t", "output": "x" * 5000})
    assert len(slim["output"]) < 700 and slim["output"].endswith("[truncated]")


# --- results ------------------------------------------------------------------------
def test_safe_error_hides_provider_details():
    raw = ("RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached in "
           "organization `org_secret123` on tokens per day (TPD)'}}")
    msg = results.safe_error(raw)
    assert "org_" not in msg and "daily token budget" in msg
    assert "org_" not in results.safe_error("SomethingElse: org_secret123 exploded")


def test_markdown_summary_table():
    rows = [{"test_case": "case", "metric": "Tool Correctness", "score": 1.0, "status": "pass"}]
    run = {"run_id": "r1", "settings": {"agent_model": "a", "judge_model": "j", "test_cases": 1,
                                        "store_today": "2026-10-16"},
           "summary": results.summarize(rows), "results": rows}
    md = results.to_markdown(run)
    assert "| Tool Correctness | 1.00 | 1 | 0 | 0 |" in md and "✅ pass" in md
