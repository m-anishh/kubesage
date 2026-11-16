# terraform init -backend-config=../backend.hcl
terraform {
  backend "s3" {
    key          = "cluster/terraform.tfstate"
    region       = "ap-south-1"
    use_lockfile = true
  }
}
