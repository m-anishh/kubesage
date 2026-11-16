variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "state_bucket" {
  description = "S3 bucket that holds Terraform state (kubesage-tfstate-<account-id>)"
  type        = string
}

variable "k8s_version" {
  description = "Use the newest version EKS offers; versions past standard support bill 6x. Check: aws eks describe-cluster-versions --region ap-south-1"
  type        = string
  default     = "1.37"
}

variable "my_ip_cidr" {
  description = "Your public IP as a /32; the only address allowed to reach the public API endpoint. scripts/up.sh sets it."
  type        = string
}

variable "node_instance_type" {
  description = "2 vCPU / 8 GB. The account is on the AWS Free plan, which only launches Free Tier eligible types: t3.large is refused, m7i-flex.large is allowed."
  type        = string
  default     = "m7i-flex.large"
}

variable "ssh_public_key" {
  description = "Contents of your SSH public key (~/.ssh/kubesage.pub). Empty disables SSH to the node."
  type        = string
  default     = ""
}

variable "bedrock_model_arns" {
  description = "Models / inference profiles the agent may invoke. Cross-region (apac.*) profiles route to models in other regions, hence the region wildcard."
  type        = list(string)
  default = [
    "arn:aws:bedrock:*::foundation-model/*",
    "arn:aws:bedrock:*:*:inference-profile/*",
  ]
}
