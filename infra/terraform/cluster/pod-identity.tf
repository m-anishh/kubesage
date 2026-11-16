# Pods get IAM roles through EKS Pod Identity: no keys, no IRSA OIDC provider per cluster.
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# --- kubesage-agent: call Bedrock, nothing else ---
resource "aws_iam_role" "agent" {
  name               = "kubesage-agent"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "agent" {
  statement {
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = var.bedrock_model_arns
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent.json
}

resource "aws_eks_pod_identity_association" "agent" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "kubesage"
  service_account = "kubesage-agent"
  role_arn        = aws_iam_role.agent.arn
  depends_on      = [aws_eks_addon.pod_identity]
}

# --- external-secrets: read only the KubeSage secrets ---
resource "aws_iam_role" "external_secrets" {
  name               = "kubesage-external-secrets"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

data "aws_iam_policy_document" "external_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [
      data.terraform_remote_state.base.outputs.github_token_secret_arn,
      data.terraform_remote_state.base.outputs.grafana_admin_secret_arn,
    ]
  }
}

resource "aws_iam_role_policy" "external_secrets" {
  name   = "read-github-token"
  role   = aws_iam_role.external_secrets.id
  policy = data.aws_iam_policy_document.external_secrets.json
}

resource "aws_eks_pod_identity_association" "external_secrets" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = aws_iam_role.external_secrets.arn
  depends_on      = [aws_eks_addon.pod_identity]
}
