# 0005: Plain final answer instead of structured output

**Status:** Accepted

## Context
The original agent returned a Pydantic `Answer` (`answer`, `conversation`) through `response_format`. On Groq:
1. Provider-side JSON mode can't be combined with tool calling (HTTP 400).
2. `ToolStrategy` (structured output as a forced tool call) sometimes failed because `gpt-oss` answered in plain text instead of calling the tool (HTTP 400 `tool_use_failed`). It also lowercased the tool name.
3. The extra "answer" tool showed up in `tools_called` and lowered Tool Correctness.

## Decision
No structured output. The agent's last message is the answer (`final_answer(response)`). The terminal chat loops until the user types `quit` instead of reading a `conversation` flag.

## Consequences
- No more flaky 400s, one fewer tool schema per call, and honest tool metrics.
- The app streams the answer token by token, which structured output would have prevented.
- There is no machine-readable "conversation finished" signal. The web UI didn't need one.
