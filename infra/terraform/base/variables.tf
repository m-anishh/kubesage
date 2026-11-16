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

variable "state_bucket" {
  description = "S3 bucket that holds Terraform state (kubesage-tfstate-<account-id>)"
  type        = string
}

variable "ecr_repositories" {
  type    = list(string)
  default = ["orders-api", "payments-api", "kubesage-agent"]
}
