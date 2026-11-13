# 0007: OIDC and least-privilege identities for CI/CD

**Status:** Accepted

## Context
GitHub Actions needs to push images and roll out revisions, and pull requests should show a `terraform plan`. Long-lived client secrets in GitHub are the usual way credentials leak.

## Decision
- **No client secrets anywhere.** GitHub's OIDC token is exchanged for Azure tokens through federated identity credentials (`terraform/2_cicd`).
- There are **two identities**:
  - **Deployer:** trusted only for `repo:<owner>/<repo>:ref:refs/heads/main`. It has `AcrPush` and `Reader` on the registry and `Contributor` on this one Container App.
  - **Planner:** trusted only for `pull_request`. It has `Reader` on the resource group, `Key Vault Secrets User`, and `Storage Blob Data Contributor` on the state account (which `terraform plan` needs for its state lock).
- Workflows **skip, not fail,** until their identity's client ID is set as a repository variable. Fork PRs never receive Azure tokens.
- Images are built with Docker on the runner, because ACR Tasks (`az acr build`) are often disabled on Azure for Students.

## Consequences
- A leaked workflow can push an image to one registry and update one app. It can't touch other resources.
- Applying `2_cicd` needs permission to create app registrations in Entra ID, which some university tenants block. Deploying by hand from a laptop still works.
