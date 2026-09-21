#!/usr/bin/env bash
set -e

# Change directory to project root if invoked from scripts/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

STACK_NAME="aws-cost-alerts-cdn"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-north-1}}"
TEMPLATE_FILE="infra/cloudfront.yaml"

if [ ! -f "$TEMPLATE_FILE" ]; then
  TEMPLATE_FILE="cloudfront.yaml"
fi

echo "=========================================="
echo " AWS Cost Alerts - CloudFront Deployment  "
echo "=========================================="
echo "Stack Name : $STACK_NAME"
echo "AWS Region : $REGION"
echo "Template   : $TEMPLATE_FILE"
echo "------------------------------------------"

echo "[1/3] Deploying CloudFormation Stack (S3 + OAC + CloudFront)..."
aws cloudformation deploy \
  --template-file "$TEMPLATE_FILE" \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "[2/3] Retrieving deployment outputs..."
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text)

WEBSITE_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" \
  --output text)

DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" \
  --output text)

echo "Created Bucket     : $BUCKET_NAME"
echo "Distribution ID    : $DIST_ID"
echo "CloudFront URL     : $WEBSITE_URL"

echo "[3/3] Uploading dashboard.html to S3 bucket..."
aws s3 cp cost_alerts/dashboard.html "s3://$BUCKET_NAME/index.html" --content-type text/html

echo ""
echo "=========================================="
echo " Deployment Successfully Completed!       "
echo " Live URL: $WEBSITE_URL                   "
echo "=========================================="
