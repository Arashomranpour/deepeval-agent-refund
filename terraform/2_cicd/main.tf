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

  # Local backend: state is stored in terraform.tfstate in this directory (gitignored).
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}

provider "azuread" {}

data "azurerm_client_config" "current" {}

# Outputs of part 1 (same machine, local state). Every value can be overridden in tfvars.
data "terraform_remote_state" "app" {
  backend = "local"
  config = {
    path = "../1_app/terraform.tfstate"
  }
}

locals {
  name_prefix = var.project_name

  acr_id           = var.acr_id != "" ? var.acr_id : try(data.terraform_remote_state.app.outputs.acr_id, "")
  container_app_id = var.container_app_id != "" ? var.container_app_id : try(data.terraform_remote_state.app.outputs.container_app_id, "")
  resource_group   = try(data.terraform_remote_state.app.outputs.resource_group_name, "")
  acr_name         = try(data.terraform_remote_state.app.outputs.acr_name, "")
  container_app    = try(data.terraform_remote_state.app.outputs.container_app_name, "")
}

# --- GitHub Actions identity (OIDC: no client secret anywhere) ----------------------
resource "azuread_application" "github" {
  display_name = "${local.name_prefix}-github-actions"
}

resource "azuread_service_principal" "github" {
  client_id = azuread_application.github.client_id
}

# Trust only workflows running on the main branch of this one repository.
resource "azuread_application_federated_identity_credential" "main_branch" {
  application_id = azuread_application.github.id
  display_name   = "github-main"
  description    = "GitHub Actions on ${var.github_repository} main branch"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:ref:refs/heads/main"
}

# --- Least privilege: push images to this registry, update this one app ---------------
resource "azurerm_role_assignment" "acr_push" {
  scope                = local.acr_id
  role_definition_name = "AcrPush"
  principal_id         = azuread_service_principal.github.object_id
}

# `az acr build` queues a cloud build, which needs to run tasks on the registry.
resource "azurerm_role_assignment" "acr_tasks" {
  scope                = local.acr_id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github.object_id
}

resource "azurerm_role_assignment" "app_update" {
  scope                = local.container_app_id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github.object_id
}
