resource "aws_ecr_repository" "this" {
  for_each             = toset(var.ecr_repositories)
  name                 = each.key
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true # lets the final `terraform destroy` of base succeed

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "keep_last_10" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
