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
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }

  # Remote state in Azure Storage (created by 0_state). Partial config:
  #   terraform init -backend-config=../backend.hcl -backend-config="key=1_app.tfstate"
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    key_vault {
      # Demo project: let `terraform destroy` fully remove the vault.
      purge_soft_delete_on_destroy = true
    }
  }
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
  # The tickets storage account has shared keys disabled: use Entra ID for data-plane calls.
  storage_use_azuread = true
}

data "azurerm_client_config" "current" {}

locals {
  name_prefix = var.project_name

  common_tags = {
    Project   = var.project_name
    Part      = "1_app"
    ManagedBy = "terraform"
  }

  # Until CI pushes the real image, run a public placeholder so the first apply works.
  image = var.container_image != "" ? var.container_image : "mcr.microsoft.com/k8se/quickstart:latest"
  port  = var.container_image != "" ? 8501 : 80
}

# Globally unique suffix for the registry name (letters/digits only).
resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "${local.name_prefix}-rg"
  location = var.location
  tags     = local.common_tags
}

# --- Logs -----------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name_prefix}-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5 # cost guard for a demo
  tags                = local.common_tags
}

# --- Telemetry: Application Insights on the same workspace -------------------------
resource "azurerm_application_insights" "main" {
  name                = "${local.name_prefix}-insights"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.common_tags
}

# --- Secrets: Key Vault (RBAC), read by the app's managed identity -----------------
resource "azurerm_key_vault" "main" {
  name                       = "${substr(replace(local.name_prefix, "-", ""), 0, 14)}kv${random_string.suffix.result}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
  tags                       = local.common_tags
}

# Whoever runs Terraform can write secrets; the app can only read them.
resource "azurerm_role_assignment" "kv_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "app_kv_reader" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# --- Refund tickets: Azure Table Storage, Entra ID only (no account keys) ----------
resource "azurerm_storage_account" "data" {
  name                            = "${substr(replace(local.name_prefix, "-", ""), 0, 14)}data${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = azurerm_resource_group.main.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  tags                            = local.common_tags
}

# The app reads/writes tickets with its managed identity (it creates the table on first use).
resource "azurerm_role_assignment" "app_tables" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# You can browse the tickets in the portal's Storage browser too.
resource "azurerm_role_assignment" "owner_tables" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Table Data Reader"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Azure RBAC takes a short while to propagate before the first secret write/read.
resource "time_sleep" "rbac_propagation" {
  depends_on = [
    azurerm_role_assignment.kv_admin,
    azurerm_role_assignment.app_kv_reader,
    azurerm_role_assignment.app_tables,
  ]
  create_duration = "60s"
}

resource "azurerm_key_vault_secret" "appinsights" {
  name         = "appinsights-connection-string"
  value        = azurerm_application_insights.main.connection_string
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [time_sleep.rbac_propagation]
}

# --- Admin sign-in for the tickets page: password generated here, kept in Key Vault ---
resource "random_password" "admin" {
  length      = 24
  special     = true
  min_special = 2
  # Characters that are safe to paste in a browser field and a shell.
  override_special = "-_.!@#"
}

resource "azurerm_key_vault_secret" "admin_password" {
  name         = "admin-password"
  value        = random_password.admin.result
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [time_sleep.rbac_propagation]
}

# --- Cost guardrail: monthly budget with e-mail alerts ------------------------------
resource "azurerm_consumption_budget_resource_group" "main" {
  count             = var.budget_alert_email != "" ? 1 : 0
  name              = "${local.name_prefix}-monthly-budget"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", plantimestamp())
  }

  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = [var.budget_alert_email]
  }

  notification {
    enabled        = true
    threshold      = 90
    operator       = "GreaterThan"
    contact_emails = [var.budget_alert_email]
  }

  lifecycle {
    ignore_changes = [time_period] # start date is fixed at creation
  }
}

# --- Container registry (images are pushed by CI or `az acr build`) ---------------
resource "azurerm_container_registry" "main" {
  name                = "${replace(local.name_prefix, "-", "")}${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.common_tags
}

# The app pulls from the registry with its own identity: no registry passwords.
resource "azurerm_user_assigned_identity" "app" {
  name                = "${local.name_prefix}-app-identity"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.common_tags
}

resource "azurerm_role_assignment" "app_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# --- Container Apps (runs the Streamlit server; WebSockets supported) -------------
resource "azurerm_container_app_environment" "main" {
  name                       = "${local.name_prefix}-env"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.common_tags
}

resource "azurerm_container_app" "app" {
  name                         = "${local.name_prefix}-app"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = local.common_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  # Pulled from Key Vault at runtime by the app's identity; never stored in the app config.
  secret {
    name                = "appinsights-connection-string"
    identity            = azurerm_user_assigned_identity.app.id
    key_vault_secret_id = azurerm_key_vault_secret.appinsights.versionless_id
  }

  secret {
    name                = "admin-password"
    identity            = azurerm_user_assigned_identity.app.id
    key_vault_secret_id = azurerm_key_vault_secret.admin_password.versionless_id
  }

  ingress {
    external_enabled = true
    target_port      = local.port
    transport        = "auto" # HTTP/1.1 + WebSockets for Streamlit

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # Scale to zero when idle (≈ no cost); first visit after idle takes a few seconds.
    min_replicas = var.min_replicas
    # One replica: Streamlit sessions live in memory, so no sticky-session setup needed.
    max_replicas = 1

    container {
      name   = "streamlit"
      image  = local.image
      cpu    = 0.5
      memory = "1Gi"

      # Bring-your-own-key app: no Groq key in the container.
      env {
        name  = "AGENT_TODAY"
        value = var.store_today
      }

      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }

      env {
        name  = "OTEL_SERVICE_NAME"
        value = "${local.name_prefix}-app"
      }

      # Refund tickets in Table Storage, reached with the managed identity below.
      env {
        name  = "AZURE_TABLES_ENDPOINT"
        value = azurerm_storage_account.data.primary_table_endpoint
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.app.client_id
      }

      # Admin sign-in for the tickets page.
      env {
        name  = "ADMIN_USERNAME"
        value = var.admin_username
      }

      env {
        name        = "ADMIN_PASSWORD"
        secret_name = "admin-password"
      }

      dynamic "liveness_probe" {
        for_each = var.container_image != "" ? [1] : []
        content {
          transport = "HTTP"
          path      = "/_stcore/health"
          port      = 8501
        }
      }
    }
  }

  lifecycle {
    # CI deploys new images (and switches the port from the placeholder's 80 to
    # Streamlit's 8501) with the Azure CLI; don't roll those back on the next apply.
    ignore_changes = [template[0].container[0].image, ingress[0].target_port]
  }

  depends_on = [azurerm_role_assignment.app_acr_pull, time_sleep.rbac_propagation]
}

# --- Optional: Azure Front Door (CDN + global edge + managed TLS) -----------------
# Off by default: Front Door Standard has a fixed monthly base fee (~$35).
resource "azurerm_cdn_frontdoor_profile" "main" {
  count               = var.enable_front_door ? 1 : 0
  name                = "${local.name_prefix}-fd"
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "Standard_AzureFrontDoor"
  tags                = local.common_tags
}

resource "azurerm_cdn_frontdoor_endpoint" "main" {
  count                    = var.enable_front_door ? 1 : 0
  name                     = "${local.name_prefix}-${random_string.suffix.result}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id
  tags                     = local.common_tags
}

resource "azurerm_cdn_frontdoor_origin_group" "app" {
  count                    = var.enable_front_door ? 1 : 0
  name                     = "streamlit"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main[0].id
  session_affinity_enabled = true

  load_balancing {}

  health_probe {
    protocol            = "Https"
    path                = "/_stcore/health"
    request_type        = "GET"
    interval_in_seconds = 120
  }
}

resource "azurerm_cdn_frontdoor_origin" "app" {
  count                          = var.enable_front_door ? 1 : 0
  name                           = "container-app"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.app[0].id
  enabled                        = true
  host_name                      = azurerm_container_app.app.ingress[0].fqdn
  origin_host_header             = azurerm_container_app.app.ingress[0].fqdn
  https_port                     = 443
  http_port                      = 80
  certificate_name_check_enabled = true
}

resource "azurerm_cdn_frontdoor_route" "app" {
  count                         = var.enable_front_door ? 1 : 0
  name                          = "default"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main[0].id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.app[0].id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.app[0].id]
  supported_protocols           = ["Http", "Https"]
  patterns_to_match             = ["/*"]
  forwarding_protocol           = "HttpsOnly"
  https_redirect_enabled        = true
  link_to_default_domain        = true
  # No caching: Streamlit pages and its WebSocket stream are dynamic.
}
