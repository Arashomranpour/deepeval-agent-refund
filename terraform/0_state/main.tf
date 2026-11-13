terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }

  # Bootstrap module: its own state stays local (it creates the remote backend
  # that 1_app and 2_cicd use). Gitignored.
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}

data "azurerm_client_config" "current" {}

locals {
  name_prefix = var.project_name

  common_tags = {
    Project   = var.project_name
    Part      = "0_state"
    ManagedBy = "terraform"
  }
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_resource_group" "state" {
  name     = "${local.name_prefix}-tfstate-rg"
  location = var.location
  tags     = local.common_tags
}

resource "azurerm_storage_account" "state" {
  name                            = "${substr(replace(local.name_prefix, "-", ""), 0, 12)}tf${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.state.name
  location                        = azurerm_resource_group.state.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false # Entra ID (RBAC) only, no storage keys
  default_to_oauth_authentication = true
  tags                            = local.common_tags

  blob_properties {
    versioning_enabled = true # every state write is recoverable
    delete_retention_policy {
      days = 14
    }
    container_delete_retention_policy {
      days = 14
    }
  }
}

resource "azurerm_storage_container" "state" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

# Subscription owners don't automatically get blob data access: grant it to whoever
# runs Terraform (you, via az login).
resource "azurerm_role_assignment" "state_admin" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Writes the backend config 1_app and 2_cicd read with -backend-config=../backend.hcl
resource "local_file" "backend_config" {
  filename = "${path.module}/../backend.hcl"
  content  = <<-EOT
    resource_group_name  = "${azurerm_resource_group.state.name}"
    storage_account_name = "${azurerm_storage_account.state.name}"
    container_name       = "${azurerm_storage_container.state.name}"
    use_azuread_auth     = true
  EOT
}
