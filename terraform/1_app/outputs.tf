output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "acr_id" {
  value = azurerm_container_registry.main.id
}

output "container_app_name" {
  value = azurerm_container_app.app.name
}

output "container_app_id" {
  value = azurerm_container_app.app.id
}

output "app_url" {
  value = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "front_door_url" {
  value = var.enable_front_door ? "https://${azurerm_cdn_frontdoor_endpoint.main[0].host_name}" : ""
}

output "setup_instructions" {
  value = <<-EOT

    App URL:        https://${azurerm_container_app.app.ingress[0].fqdn}
    ${var.enable_front_door ? "Front Door URL: https://${azurerm_cdn_frontdoor_endpoint.main[0].host_name}" : "Front Door:     disabled (set enable_front_door = true)"}

    1. Build the image in Azure (no local Docker needed), from the repo root:
       az acr build --registry ${azurerm_container_registry.main.name} --image deepeval-agent-refund:v1 .

    2. Point the app at it, either:
       - set container_image = "${azurerm_container_registry.main.login_server}/deepeval-agent-refund:v1"
         in terraform.tfvars, then: terraform plan -out=tfplan && terraform apply tfplan
       - or let CI deploy it (terraform/2_cicd), which runs `az containerapp update` on every push.

    3. GitHub repository variables for CI (gh variable set NAME --body VALUE):
       AZURE_RESOURCE_GROUP = ${azurerm_resource_group.main.name}
       AZURE_ACR_NAME       = ${azurerm_container_registry.main.name}
       AZURE_CONTAINER_APP  = ${azurerm_container_app.app.name}

  EOT
}
