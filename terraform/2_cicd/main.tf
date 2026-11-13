terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }

  # Remote state in Azure Storage (created by 0_state). Partial config:
  #   terraform init -backend-config=../backend.hcl -backend-config="key=2_cicd.tfstate"
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}

provider "azuread" {}

data "azurerm_client_config" "current" {}

# Outputs of part 1, read from the shared remote state. Values can be overridden in tfvars.
data "terraform_remote_state" "app" {
  backend = "azurerm"
  config = {
    resource_group_name  = var.tfstate_resource_group
    storage_account_name = var.tfstate_storage_account
    container_name       = "tfstate"
    key                  = "1_app.tfstate"
    use_azuread_auth     = true
  }
}

locals {
  name_prefix = var.project_name
  app         = data.terraform_remote_state.app.outputs

  acr_id            = var.acr_id != "" ? var.acr_id : try(local.app.acr_id, "")
  container_app_id  = var.container_app_id != "" ? var.container_app_id : try(local.app.container_app_id, "")
  resource_group_id = try(local.app.resource_group_id, "")
  key_vault_id      = try(local.app.key_vault_id, "")
  resource_group    = try(local.app.resource_group_name, "")
  acr_name          = try(local.app.acr_name, "")
  container_app     = try(local.app.container_app_name, "")
}

data "azurerm_storage_account" "state" {
  name                = var.tfstate_storage_account
  resource_group_name = var.tfstate_resource_group
}

# =====================================================================================
# 1. Deployer: GitHub Actions on main. Pushes images and updates this one app.
# =====================================================================================
resource "azuread_application" "deployer" {
  display_name = "${local.name_prefix}-github-deployer"
}

resource "azuread_service_principal" "deployer" {
  client_id = azuread_application.deployer.client_id
}

resource "azuread_application_federated_identity_credential" "deployer_main" {
  application_id = azuread_application.deployer.id
  display_name   = "github-main"
  description    = "GitHub Actions on ${var.github_repository} main branch"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:ref:refs/heads/main"
}

# Images are built with Docker on the runner and pushed (ACR Tasks / `az acr build` are
# often disabled on Azure for Students), so pushing and reading the registry is enough.
resource "azurerm_role_assignment" "deployer_acr_push" {
  scope                = local.acr_id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.deployer.object_id
}

resource "azurerm_role_assignment" "deployer_acr_read" {
  scope                = local.acr_id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.deployer.object_id
}

resource "azurerm_role_assignment" "deployer_app" {
  scope                = local.container_app_id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.deployer.object_id
}

# =====================================================================================
# 2. Planner: GitHub Actions on pull requests. Read-only: runs `terraform plan` for 1_app.
# =====================================================================================
resource "azuread_application" "planner" {
  display_name = "${local.name_prefix}-github-planner"
}

resource "azuread_service_principal" "planner" {
  client_id = azuread_application.planner.client_id
}

resource "azuread_application_federated_identity_credential" "planner_pr" {
  application_id = azuread_application.planner.id
  display_name   = "github-pull-requests"
  description    = "terraform plan on pull requests to ${var.github_repository}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:pull_request"
}

resource "azurerm_role_assignment" "planner_read" {
  scope                = local.resource_group_id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.planner.object_id
}

# Plan refreshes the Key Vault secret resource, so it needs to read secret metadata/values.
resource "azurerm_role_assignment" "planner_kv" {
  scope                = local.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azuread_service_principal.planner.object_id
}

# Read + lock the remote state (plan takes a blob lease).
resource "azurerm_role_assignment" "planner_state" {
  scope                = data.azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.planner.object_id
}
