#!/usr/bin/env bash
# Start of every session: create the EKS cluster and its t3.large node (~15 min).
set -euo pipefail
cd "$(dirname "$0")/.."
START=$(date +%s)

TF_VAR_my_ip_cidr="$(curl -s https://checkip.amazonaws.com | tr -d '[:space:]')/32"
export TF_VAR_my_ip_cidr
echo "Your public IP: $TF_VAR_my_ip_cidr"

if [ -f "$HOME/.ssh/kubesage.pub" ]; then
  TF_VAR_ssh_public_key="$(cat "$HOME/.ssh/kubesage.pub")"
  export TF_VAR_ssh_public_key
  echo "SSH key found: SSH to the node is enabled from your IP only"
fi

terraform -chdir=infra/terraform/cluster init -input=false -backend-config=../backend.hcl
terraform -chdir=infra/terraform/cluster apply -auto-approve

aws eks update-kubeconfig --name kubesage --region ap-south-1
kubectl get nodes

bash scripts/bootstrap-argocd.sh

echo "Cluster up in $(( ($(date +%s) - START) / 60 )) minutes. Billing is ON: run 'bash scripts/down.sh' when you finish."
terraform -chdir=infra/terraform/cluster output
