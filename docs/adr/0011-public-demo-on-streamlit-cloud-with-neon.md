# 0011: Public demo on Streamlit Community Cloud, tickets in Postgres

**Status:** Accepted

## Context
The project needs a free, always-available public link for a CV. The Azure stack ([0001](0001-container-apps-not-static-cdn.md)) is ready in Terraform but costs money, so it stays the documented production path rather than the demo host.

**Vercel** was evaluated. It runs Docker images and supports WebSockets, so the app could run there, but each WebSocket is capped at the function's maximum duration (5 minutes on the free plan) with no instance affinity. A Streamlit session (chat history, the visitor's key, the sign-in) could reset mid-demo. Its containers are also stateless.

## Decision
- Host the demo on **Streamlit Community Cloud**: free, built for long-lived Streamlit sessions, and redeployed on every push to `main`. It installs from `requirements.txt`, exported from `uv.lock`; CI fails if the two drift.
- `agent/tickets.py` gains a **Postgres** backend, selected when `DATABASE_URL` is set (a free **Neon** database), because the Community Cloud disk is wiped on restart. Without it, tickets fall back to SQLite and last until the next restart.
- Settings come from Community Cloud **secrets**. `app.py` copies `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `DATABASE_URL` and `AGENT_TODAY` into the environment, so the code reads configuration one way everywhere. There is no Groq key in the secrets ([0006](0006-bring-your-own-key.md)).

## Consequences
- A free public link with stable sessions; Azure remains the production design.
- Community Cloud apps sleep after a period without visitors; the first visitor wakes it with one click.
- No managed identity on Community Cloud, so the database URL is a secret in its dashboard, scoped to one database of demo tickets.
