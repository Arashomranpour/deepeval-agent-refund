# 0006: Bring-your-own-key for the public app

**Status:** Accepted

## Context
The app is public. If it ran on the owner's Groq key, anyone could use up the daily quota, and provider error messages (which include the organization ID) could reach visitors.

## Decision
- The chat page is gated: visitors paste their own Groq key in a password field inside a form with `clear_on_submit`. The key is validated by listing models, which spends no tokens.
- The key and the agent built from it live only in `st.session_state`, never in caches, files, logs, URLs or telemetry. There is a "Forget key" button.
- Only friendly errors are shown (rate limit, rejected key), and raw errors are logged server-side. Saved evaluation results are sanitized the same way (`results.safe_error`).
- There is a limit of 20 messages per session.
- `GROQ_API_KEY` from `.env` is used only by command-line scripts and the manual Eval workflow, never by the deployed container.

## Consequences
- The deployment needs no LLM secret at all, and the owner's quota can't be abused.
- Visitors need a free Groq account to try the chat. The Evaluation results page works without a key.
