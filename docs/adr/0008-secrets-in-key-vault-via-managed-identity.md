# 0008: App secrets in Key Vault, read by managed identity

**Status:** Accepted

## Context
The container needs the Application Insights connection string. Putting it in plain environment variables or Terraform outputs spreads it into logs, state diffs and CI output.

## Decision
- **Key Vault** uses the RBAC permission model (no access policies). The person running Terraform gets `Key Vault Secrets Officer`; the app's **user-assigned managed identity** gets only `Key Vault Secrets User`.
- The Container App declares a secret with `key_vault_secret_id` (versionless) and the identity, and exposes it as `APPLICATIONINSIGHTS_CONNECTION_STRING` through `secret_name`. The value never appears in the app's configuration.
- The same identity pulls images (`AcrPull`), so the registry has no admin user or password.
- A `time_sleep` waits for RBAC propagation before the first secret write.
- Terraform state is in Azure Storage with **Entra ID auth only** (`shared_access_key_enabled = false`) and blob versioning, because state can hold secret values.

## Consequences
- Rotating the secret means updating the vault and restarting the revision; no redeploy is needed.
- The state still contains the secret value, as all Terraform state does. That is why the state is remote, private, versioned and key-less.
