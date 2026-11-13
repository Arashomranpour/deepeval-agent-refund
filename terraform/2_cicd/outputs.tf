output "deployer_client_id" {
  value = azuread_application.deployer.client_id
}

output "planner_client_id" {
  value = azuread_application.planner.client_id
}

output "azure_tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "azure_subscription_id" {
  value = data.azurerm_client_config.current.subscription_id
}

output "setup_instructions" {
  value = <<-EOT

    Set these GitHub repository variables (IDs, not secrets: OIDC needs no password):

    gh variable set AZURE_CLIENT_ID         --repo ${var.github_repository} --body ${azuread_application.deployer.client_id}
    gh variable set AZURE_PLANNER_CLIENT_ID --repo ${var.github_repository} --body ${azuread_application.planner.client_id}
    gh variable set AZURE_TENANT_ID         --repo ${var.github_repository} --body ${data.azurerm_client_config.current.tenant_id}
    gh variable set AZURE_SUBSCRIPTION_ID   --repo ${var.github_repository} --body ${data.azurerm_client_config.current.subscription_id}
    gh variable set AZURE_RESOURCE_GROUP    --repo ${var.github_repository} --body ${local.resource_group}
    gh variable set AZURE_ACR_NAME          --repo ${var.github_repository} --body ${local.acr_name}
    gh variable set AZURE_CONTAINER_APP     --repo ${var.github_repository} --body ${local.container_app}
    gh variable set TFSTATE_RESOURCE_GROUP  --repo ${var.github_repository} --body ${var.tfstate_resource_group}
    gh variable set TFSTATE_STORAGE_ACCOUNT --repo ${var.github_repository} --body ${var.tfstate_storage_account}

    Deploy workflow skips until AZURE_CLIENT_ID is set; Terraform plan workflow until
    AZURE_PLANNER_CLIENT_ID is set. Then: gh workflow run deploy.yml && gh run watch

  EOT
}
