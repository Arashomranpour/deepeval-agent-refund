# 0012: Clerk sign-in for the chat page, through OpenID Connect

**Status:** Accepted

## Context
The public chat should know who is using it (to deter abuse and to look like a real product), without slowing down someone opening the link from a CV. Clerk has no Streamlit SDK.

## Decision
- Use **Clerk as an OpenID Connect provider**: an OAuth application in the Clerk dashboard (confidential client, scopes `openid email profile`), and Streamlit's built-in **`st.login("clerk")`** with Clerk's discovery URL. No Clerk JavaScript is embedded.
- **Chat page only.** Visitors sign in with email, Google or GitHub, then bring their own Groq key as before ([0006](0006-bring-your-own-key.md)). The **Evaluation results** page stays public. The **admin** page keeps its own username and password ([0010](0010-refund-tickets-in-table-storage.md)), so back-office access doesn't depend on the customer identity provider.
- Configuration lives in Streamlit secrets (`[auth]`, `[auth.clerk]`). When it is absent (local runs without `secrets.toml`, tests), the chat stays open, so the app works out of the box.
- Signing out also forgets the Groq key. The user's name and e-mail are only shown in the sidebar: never sent to the model, logs or telemetry.

## Consequences
- Real sign-in with social login and MFA, managed by Clerk, at no cost on its free plan.
- One more redirect URI to register per deployment (`http://localhost:8501/oauth2callback`, `https://<app>.streamlit.app/oauth2callback`).
- The Clerk instance is in **Development** mode, which shows a "Development mode" badge and has user limits; a production instance needs a custom domain.
