# 0002: Run on Groq's free tier; slim traces before judging

**Status:** Accepted

## Context
The project moved from OpenAI to Groq (`openai/gpt-oss-120b`) through `langchain-groq`. On the free tier, each model allows about **8k tokens per minute, per request too**, and **200k tokens per day**. The four DeepEval trace metrics send the agent's whole trace to the judge. A raw LangGraph trace for one refund was about **10.5k tokens**, because every LLM span repeats the system prompt and tool schemas and every graph-node span repeats the message history. All four metrics failed with HTTP 413.

## Decision
- `evaluations/slim_trace.py` patches DeepEval's trace builder to drop LLM-span inputs and duplicate graph-node payloads, keep the user input, every tool call and its output, each LLM decision, and the final answer, and truncate long values. The trace shrank from 32k characters to 4.4k (about 1.3k tokens).
- Models run with `reasoning_effort="low"`, `max_tokens=1024` and `max_retries=6`. The judge runs sequentially (`run_async=False`) with a 15-minute budget per metric, `EVAL_LIMIT` (default 2 goldens), and `ErrorConfig(ignore_errors=True)`, so a rate-limited metric shows as an error instead of killing the run.

## Consequences
- The whole pipeline runs at no cost, but a full 7-golden run takes minutes and must stay under the daily budget.
- Monkey-patching a DeepEval internal (`trace_manager.create_nested_spans_dict`) is fragile across DeepEval upgrades. It is covered by unit tests, and `deepeval` is pinned through `uv.lock`.
- The judge sees less raw context. In practice that is the information that matters for behavior metrics.
