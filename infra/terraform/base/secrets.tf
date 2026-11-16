# Created empty. Set the value from the CLI so it never lands in Terraform state:
#   aws secretsmanager put-secret-value --secret-id kubesage/github-token --secret-string <PAT>
resource "aws_secretsmanager_secret" "github_token" {
  name                    = "kubesage/github-token"
  description             = "Fine-grained PAT: Issues write on kubesage, Contents read on kubesage-gitops"
  recovery_window_in_days = 0
}

# Grafana admin login, JSON {"admin-user": "...", "admin-password": "..."}, set from the CLI.
# Without a fixed secret the Grafana chart generates a new random password on every ArgoCD render,
# which restarts Grafana and logs everyone out every few minutes.
resource "aws_secretsmanager_secret" "grafana_admin" {
  name                    = "kubesage/grafana-admin"
  description             = "Grafana admin user and password, synced into the cluster by External Secrets"
  recovery_window_in_days = 0
}
