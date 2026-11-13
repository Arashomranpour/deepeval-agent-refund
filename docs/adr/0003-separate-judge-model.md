# 0003: Judge with a different model from the agent

**Status:** Accepted

## Context
At first, the agent and the DeepEval judge were both `openai/gpt-oss-120b`. Two problems showed up. A model grading its own output is biased toward it. And on Groq's free tier both shared one 200k-token daily budget, which a single day of agent testing plus evaluation ran out of (HTTP 429, "tokens per day").

## Decision
The judge defaults to `openai/gpt-oss-20b` (override with `JUDGE_MODEL`), wrapped in a `DeepEvalBaseLLM` subclass. Its structured outputs use Groq's JSON-schema mode, because the default tool-calling mode failed with `tool_use_failed`.

## Consequences
- The agent no longer grades itself, and the evaluation capacity per day is doubled.
- A smaller judge can be less accurate on nuanced rubrics. With a paid key, set `JUDGE_MODEL` to a stronger model; the agent is unaffected.
