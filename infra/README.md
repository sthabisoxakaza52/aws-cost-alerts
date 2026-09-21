# Cloud Infrastructure Templates

This directory contains Infrastructure as Code (IaC) templates for automated provisioning of AWS cloud resources.

## Files

| File | Type | Description |
|---|---|---|
| [`cloudfront.yaml`](cloudfront.yaml) | AWS CloudFormation | CloudFront HTTPS CDN with Origin Access Control (OAC) and secure Amazon S3 static web hosting bucket. |

## Resources Provisioned by `cloudfront.yaml`

1. **Amazon S3 Bucket (`AWS::S3::Bucket`)**:
   - AES256 server-side encryption enabled by default.
   - Public access blocks enforced (`BlockPublicAcls`, `BlockPublicPolicy`, `IgnorePublicAcls`, `RestrictPublicBuckets`).
2. **CloudFront Origin Access Control (`AWS::CloudFront::OriginAccessControl`)**:
   - SigV4 request signing ensuring S3 bucket is only accessible through the CloudFront distribution.
3. **CloudFront Distribution (`AWS::CloudFront::Distribution`)**:
   - Configured with `redirect-to-https`, HTTP/2, and default root object `index.html`.
4. **S3 Bucket Policy (`AWS::S3::BucketPolicy`)**:
   - Least-privilege policy granting read access solely to the CloudFront distribution ARN.

## Deployment Command

```bash
aws cloudformation deploy \
  --template-file infra/cloudfront.yaml \
  --stack-name aws-cost-alerts-cdn \
  --region eu-north-1
```
