# Architecture decision records

Short records of the decisions that shaped this project: the context, what we chose, and what it costs us. Format: [Michael Nygard's ADR template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

| # | Decision | Status |
|---|---|---|
| [0001](0001-container-apps-not-static-cdn.md) | Host Streamlit on Azure Container Apps; Front Door is an optional CDN | Accepted |
| [0002](0002-groq-free-tier-and-trace-slimming.md) | Run on Groq's free tier; slim traces before judging | Accepted |
| [0003](0003-separate-judge-model.md) | Judge with a different model from the agent | Accepted |
| [0004](0004-fixed-store-date.md) | Freeze the store date | Accepted |
| [0005](0005-plain-answer-not-structured-output.md) | Plain final answer instead of structured output | Accepted |
| [0006](0006-bring-your-own-key.md) | Bring-your-own-key for the public app | Accepted |
| [0007](0007-oidc-and-least-privilege.md) | OIDC and least-privilege identities for CI/CD | Accepted |
| [0008](0008-secrets-in-key-vault-via-managed-identity.md) | App secrets in Key Vault, read by managed identity | Accepted |
| [0009](0009-evaluate-behaviour-not-just-answers.md) | Gate quality on behavior metrics, not answer text | Accepted |
| [0010](0010-refund-tickets-in-table-storage.md) | Refund tickets in Azure Table Storage, reviewed on an admin page | Accepted |
