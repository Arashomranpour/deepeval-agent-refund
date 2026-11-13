output "state_resource_group" {
  value = azurerm_resource_group.state.name
}

output "state_storage_account" {
  value = azurerm_storage_account.state.name
}

output "state_storage_account_id" {
  value = azurerm_storage_account.state.id
}

output "state_container" {
  value = azurerm_storage_container.state.name
}

output "setup_instructions" {
  value = <<-EOT

    Remote state is ready. terraform/backend.hcl was written (gitignored).
    Wait ~1 minute for the blob role to propagate, then in 1_app and 2_cicd:

      terraform init -backend-config=../backend.hcl -backend-config="key=<module>.tfstate"

    For CI (terraform plan on pull requests), set these repository variables:
      gh variable set TFSTATE_RESOURCE_GROUP  --body ${azurerm_resource_group.state.name}
      gh variable set TFSTATE_STORAGE_ACCOUNT --body ${azurerm_storage_account.state.name}

  EOT
}
