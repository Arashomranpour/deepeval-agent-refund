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

    The app now serves a placeholder page. To ship the real image:

    Option A (recommended): GitHub Actions
       cd ../2_cicd, apply it, run the gh variable set commands it prints, then:
       gh workflow run deploy.yml --repo <owner>/deepeval-agent-refund && gh run watch

    Option B: from this machine (needs Docker Desktop running), repo root:
       az acr login --name ${azurerm_container_registry.main.name}
       docker build -t ${azurerm_container_registry.main.login_server}/deepeval-agent-refund:v1 .
       docker push ${azurerm_container_registry.main.login_server}/deepeval-agent-refund:v1
       az containerapp ingress update -n ${azurerm_container_app.app.name} -g ${azurerm_resource_group.main.name} --target-port 8501
       az containerapp update -n ${azurerm_container_app.app.name} -g ${azurerm_resource_group.main.name} \
         --image ${azurerm_container_registry.main.login_server}/deepeval-agent-refund:v1

  EOT
}

output "resource_group_id" {
  value = azurerm_resource_group.main.id
}

output "key_vault_id" {
  value = azurerm_key_vault.main.id
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "application_insights_name" {
  value = azurerm_application_insights.main.name
}
