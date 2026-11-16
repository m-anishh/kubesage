data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "kubesage-eks-node"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore", # shell access with no open port: aws ssm start-session
  ])
  role       = aws_iam_role.node.name
  policy_arn = each.value
}

# --- Optional SSH, only from var.my_ip_cidr ---
locals {
  ssh_enabled = var.ssh_public_key != ""
}

resource "aws_key_pair" "node" {
  count      = local.ssh_enabled ? 1 : 0
  key_name   = "kubesage-node"
  public_key = var.ssh_public_key
}

# EKS opens port 22 to 0.0.0.0/0 when remote_access has a key but no source security group.
# This empty group is that source, so the rule EKS creates matches nobody; the real
# access is the my-IP rule below.
resource "aws_security_group" "ssh_source" {
  count       = local.ssh_enabled ? 1 : 0
  name        = "kubesage-ssh-source"
  description = "Empty source group: stops EKS opening SSH to the internet"
  vpc_id      = data.terraform_remote_state.base.outputs.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "ssh_my_ip" {
  count             = local.ssh_enabled ? 1 : 0
  security_group_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  description       = "SSH to the node from my public IP only"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "workers"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = local.subnet_ids
  instance_types  = [var.node_instance_type]
  disk_size       = 30

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 1
  }

  update_config {
    max_unavailable = 1
  }

  dynamic "remote_access" {
    for_each = local.ssh_enabled ? [1] : []
    content {
      ec2_ssh_key               = aws_key_pair.node[0].key_name
      source_security_group_ids = [aws_security_group.ssh_source[0].id]
    }
  }

  tags = { Name = "kubesage-node" }

  depends_on = [aws_iam_role_policy_attachment.node]
}
