#!/usr/bin/env bash
# End of every session: destroy the cluster stack so EKS stops billing.
set -euo pipefail
cd "$(dirname "$0")/.."
START=$(date +%s)

# Destroy still needs every required variable, even though the value doesn't matter.
TF_VAR_my_ip_cidr="$(curl -s https://checkip.amazonaws.com | tr -d '[:space:]')/32"
export TF_VAR_my_ip_cidr
if [ -f "$HOME/.ssh/kubesage.pub" ]; then
  TF_VAR_ssh_public_key="$(cat "$HOME/.ssh/kubesage.pub")"
  export TF_VAR_ssh_public_key
fi

terraform -chdir=infra/terraform/cluster destroy -auto-approve

echo "Cluster destroyed in $(( ($(date +%s) - START) / 60 )) minutes. Billing stopped."
