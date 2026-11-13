# 0010: Refund tickets in Azure Table Storage, reviewed on an admin page

**Status:** Accepted

## Context
`issue_refund_ticket` only returned the sentence "a refund ticket has been issued". Nothing was saved, so no one could check, approve or reject refunds. A support workflow needs a durable ticket list and a separate, signed-in role to review it. The app scales to zero on Container Apps, so anything stored on the container's disk is lost.

## Decision
- **Storage:** `agent/tickets.py` defines one small interface with three backends:
  - **Azure Table Storage** when `AZURE_TABLES_ENDPOINT` is set. The account has shared keys disabled, and the app reaches it with its user-assigned managed identity (`Storage Table Data Contributor`), using `DefaultAzureCredential`. The app creates the table on first use.
  - **SQLite** (`data/tickets.db`, gitignored) on a laptop.
  - **In-memory** for tests and evaluation runs, so eval traffic never reaches the admin's list.
- **Tool:** `issue_refund_ticket` saves a ticket (`RF-YYYYMMDD-XXXXXX`, customer, items, amount, status `open`) and returns the ticket ID for the agent to give the customer. If the store is down it says no ticket was issued, so the agent can't claim a refund that doesn't exist ([0009](0009-evaluate-behaviour-not-just-answers.md)).
- **Admin page:** a separate Streamlit page with **its own admin username and password**, independent of the visitor's Groq key ([0006](0006-bring-your-own-key.md)). Credentials are compared in constant time (`hmac.compare_digest`), five failed attempts lock the session for 60 seconds, and nothing about the tickets is shown before sign-in. Signed in, the admin can filter tickets and approve or reject open ones with a note; the reviewer and time are recorded.
- **Credentials:** locally from the gitignored `.env`. On Azure, Terraform generates the password (`random_password`), stores it in **Key Vault**, and the Container App reads it as a Key Vault secret reference ([0008](0008-secrets-in-key-vault-via-managed-identity.md)). It's retrieved with `az keyvault secret show` and never printed by Terraform.

## Alternatives
- **Django admin:** a full second web app, host and auth system for one table.
- **Cosmos DB:** a richer database, but more setup and cost than a single partition of small rows needs.
- **Microsoft Entra ID sign-in (Easy Auth):** the production choice for staff accounts, but it applies to the whole app, and visitors must stay anonymous. Kept as a future step.

## Consequences
- Tickets survive restarts and scale-to-zero, at a cost of cents per month, with no storage keys anywhere.
- A single shared admin account has no per-person audit trail beyond the username. Entra ID sign-in would fix that.
- The generated admin password lives in Terraform state, which is why state is remote, private and Entra-only ([0008](0008-secrets-in-key-vault-via-managed-identity.md)).
