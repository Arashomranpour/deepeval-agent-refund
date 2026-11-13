variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = ""
}

variable "project_name" {
  description = "Prefix for resource names (match 1_app)"
  type        = string
  default     = "deepeval-refund"
}

variable "location" {
  description = "Azure region (must be allowed by the subscription's policy)"
  type        = string
  default     = "germanywestcentral"
}
