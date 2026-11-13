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
  }

  # Local backend: state is stored in terraform.tfstate in this directory (gitignored).
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
    # CI deploys new images with `az containerapp update`; don't roll them back.
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.app_acr_pull]
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
