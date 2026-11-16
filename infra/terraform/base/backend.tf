# Bucket name comes from ../backend.hcl (git-ignored, written by scripts/setup-state.sh):
#   terraform init -backend-config=../backend.hcl
terraform {
  backend "s3" {
    key          = "base/terraform.tfstate"
    region       = "ap-south-1"
    use_lockfile = true
  }
}
