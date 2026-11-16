variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "github_owner" {
  type    = string
  default = "m-anishh"
}

variable "github_repo" {
  type    = string
  default = "kubesage"
}

variable "github_owner_id" {
  description = "Numeric GitHub user ID (gh api users/<owner> --jq .id), used in the immutable OIDC subject"
  type        = string
  default     = "163387487"
}

variable "github_repo_id" {
  description = "Numeric GitHub repo ID (gh api repos/<owner>/<repo> --jq .id), used in the immutable OIDC subject"
  type        = string
  default     = "1460193142"
}

variable "state_bucket" {
  description = "S3 bucket that holds Terraform state (kubesage-tfstate-<account-id>)"
  type        = string
}

variable "ecr_repositories" {
  type    = list(string)
  default = ["orders-api", "payments-api", "kubesage-agent"]
}
