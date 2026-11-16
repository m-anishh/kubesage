output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "node_ssh_hint" {
  value = local.ssh_enabled ? "ssh -i ~/.ssh/kubesage ec2-user@$(aws ec2 describe-instances --region ${var.region} --filters Name=tag:eks:nodegroup-name,Values=workers Name=instance-state-name,Values=running --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)" : "SSH disabled: set ssh_public_key"
}

output "ec2_console_url" {
  value = "https://${var.region}.console.aws.amazon.com/ec2/home?region=${var.region}#Instances:tag:eks:nodegroup-name=workers;instanceState=running"
}

output "agent_role_arn" {
  value = aws_iam_role.agent.arn
}
