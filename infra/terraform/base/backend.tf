# Bucket name comes from ../backend.hcl (git-ignored) so the account ID stays out of Git:
#   terraform init -backend-config=../backend.hcl
terraform {
  backend "s3" {
    key          = "base/terraform.tfstate"
    region       = "ap-south-1"
    use_lockfile = true
  }
}
