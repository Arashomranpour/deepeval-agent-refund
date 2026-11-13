#!/usr/bin/env bash
# One-time Azure preparation before `terraform apply` (safe to re-run).
#   - checks the CLI can get a token
#   - registers the resource providers this project uses
#   - prints the regions your subscription's policy allows
#   - writes subscription_id into terraform/*/terraform.tfvars (gitignored)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Azure login"
if ! az account get-access-token --output none 2>/dev/null; then
  echo "The Azure CLI can't get a token. Run:  az login" >&2
  exit 1
fi
SUB_ID=$(az account show --query id -o tsv)
echo "Subscription: $(az account show --query name -o tsv)"

echo "== Registering resource providers (first time can take a few minutes)"
for ns in Microsoft.App Microsoft.ContainerRegistry Microsoft.OperationalInsights \
          Microsoft.ManagedIdentity Microsoft.Cdn; do
  state=$(az provider show -n "$ns" --query registrationState -o tsv)
  if [ "$state" != "Registered" ]; then
    az provider register -n "$ns" --wait --output none
    state=$(az provider show -n "$ns" --query registrationState -o tsv)
  fi
  echo "  $ns: $state"
done

echo "== Allowed regions (from Azure Policy; empty = no restriction found)"
az policy assignment list \
  --query "[].parameters.listOfAllowedLocations.value[]" -o tsv 2>/dev/null | sort -u | tr '\n' ' '
echo

echo "== terraform.tfvars"
for module in 1_app 2_cicd; do
  f="terraform/$module/terraform.tfvars"
  [ -f "$f" ] || cp "terraform/$module/terraform.tfvars.example" "$f"
  sed -i.bak "s|^subscription_id *=.*|subscription_id   = \"$SUB_ID\"|" "$f" && rm -f "$f.bak"
  echo "  $f: subscription_id set"
done
echo "Next: set 'location' in terraform/1_app/terraform.tfvars to an allowed region, then"
echo "      cd terraform/1_app && terraform init && terraform plan -out=tfplan"
