#!/usr/bin/env bash
# Phase 1, run once: create the S3 bucket that stores Terraform state,
# and write the git-ignored files that tell Terraform its name.
set -euo pipefail
cd "$(dirname "$0")/../infra/terraform"

REGION=ap-south-1
ACCT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="kubesage-tfstate-$ACCT"
echo "AWS identity: $(aws sts get-caller-identity --query Arn --output text)"

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket $BUCKET already exists"
else
  echo "Creating bucket $BUCKET"
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
fi

aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "bucket = \"$BUCKET\"" > backend.hcl
echo "state_bucket = \"$BUCKET\"" > base/terraform.tfvars
echo "state_bucket = \"$BUCKET\"" > cluster/terraform.tfvars

echo "Done: state bucket ready, backend.hcl and terraform.tfvars written."
