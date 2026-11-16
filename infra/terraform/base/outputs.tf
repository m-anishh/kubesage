output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "ecr_registry" {
  value = split("/", aws_ecr_repository.this["kubesage-agent"].repository_url)[0]
}

output "ecr_repository_urls" {
  value = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "gha_push_role_arn" {
  value = aws_iam_role.gha_push.arn
}

output "gha_plan_role_arn" {
  value = aws_iam_role.gha_plan.arn
}

output "github_token_secret_arn" {
  value = aws_secretsmanager_secret.github_token.arn
}
