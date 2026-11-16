#!/usr/bin/env bash
# Phase 1, run once: create the long-lived base stack
# (VPC, subnets, ECR, GitHub OIDC roles, empty GitHub-token secret).
set -euo pipefail
cd "$(dirname "$0")/../infra/terraform/base"

terraform init -input=false -backend-config=../backend.hcl
terraform apply   # shows the plan, then asks you to type "yes"
