# Operational & Deployment Scripts

This directory contains shell and automation scripts for managing and deploying the project.

## Scripts

| Script | Runtime | Description |
|---|---|---|
| [`deploy_cloudfront.sh`](deploy_cloudfront.sh) | Bash | Automated 1-command deployment script for AWS CloudShell. Deploys the CloudFormation stack, uploads `cost_alerts/dashboard.html` to S3, and outputs the live HTTPS CloudFront URL. |

## Usage

In AWS CloudShell:
```bash
chmod +x scripts/deploy_cloudfront.sh
./scripts/deploy_cloudfront.sh
```

Or pass custom region:
```bash
AWS_REGION=us-east-1 ./scripts/deploy_cloudfront.sh
```
