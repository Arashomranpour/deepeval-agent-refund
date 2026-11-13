variable "subscription_id" {
  description = "Azure subscription ID (leave empty to use the one `az login` selected)"
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Prefix for every resource name (lowercase letters, digits, hyphens)"
  type        = string
  default     = "deepeval-refund"
}

variable "location" {
  description = "Azure region. Azure for Students only allows some regions; check the 'Allowed locations' policy."
  type        = string
  default     = "germanywestcentral"
}

variable "container_image" {
  description = "Full image reference, e.g. <registry>.azurecr.io/deepeval-agent-refund:<sha>. Empty = placeholder image until the first build."
  type        = string
  default     = ""
}

variable "min_replicas" {
  description = "0 = scale to zero when idle (cheapest, cold start); 1 = always warm (costs ~$15-20/month)"
  type        = number
  default     = 0
}

variable "store_today" {
  description = "Fixed store date the agent uses for the 30-day refund rule"
  type        = string
  default     = "2026-10-16"
}

variable "enable_front_door" {
  description = "Put Azure Front Door (CDN, edge TLS) in front of the app. Has a fixed monthly base fee."
  type        = bool
  default     = false
}

variable "budget_alert_email" {
  description = "E-mail for monthly budget alerts (50% forecast, 90% actual). Empty = no budget."
  type        = string
  default     = ""
}

variable "monthly_budget" {
  description = "Monthly budget for the resource group, in the billing currency"
  type        = number
  default     = 10
}

variable "admin_username" {
  description = "Username for the app's admin (refund tickets) page. The password is generated and stored in Key Vault."
  type        = string
  default     = "admin"
}
