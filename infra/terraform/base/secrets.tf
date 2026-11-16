# Created empty. Set the value from the CLI so it never lands in Terraform state:
#   aws secretsmanager put-secret-value --secret-id kubesage/github-token --secret-string <PAT>
resource "aws_secretsmanager_secret" "github_token" {
  name                    = "kubesage/github-token"
  description             = "Fine-grained PAT: Issues write on kubesage, Contents read on kubesage-gitops"
  recovery_window_in_days = 0
}
