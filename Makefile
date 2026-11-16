# Needs make (Git Bash: choco install make). Without make, run the scripts with bash.
.PHONY: state base up down

state:   ## once: S3 bucket for Terraform state
	bash scripts/setup-state.sh

base:    ## once: VPC, ECR, GitHub OIDC roles, secret
	bash scripts/base-apply.sh

up:      ## every session start: EKS cluster + t3.large node
	bash scripts/up.sh

down:    ## every session end: destroy the cluster, stop billing
	bash scripts/down.sh
