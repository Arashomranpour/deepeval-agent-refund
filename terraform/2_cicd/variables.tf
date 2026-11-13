variable "subscription_id" {
  description = "Azure subscription ID (leave empty to use the one `az login` selected)"
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Prefix for resource names (match 1_app)"
  type        = string
  default     = "deepeval-refund"
}

variable "github_repository" {
  description = "GitHub repository allowed to deploy, as owner/name"
  type        = string
  default     = "Arashomranpour/deepeval-agent-refund"
}

variable "acr_id" {
  description = "Override: registry resource ID (default: read from ../1_app state)"
  type        = string
  default     = ""
}

variable "container_app_id" {
  description = "Override: container app resource ID (default: read from ../1_app state)"
  type        = string
  default     = ""
}

variable "tfstate_resource_group" {
  description = "Resource group of the Terraform state storage account (output of 0_state)"
  type        = string
}

variable "tfstate_storage_account" {
  description = "Terraform state storage account name (output of 0_state)"
  type        = string
}
