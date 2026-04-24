# AWS Cost Alert Setup

A Python/Boto3 script that provisions AWS Budget alerts with **email (SNS)** and **Slack** notifications at 50%, 80%, 100%, and forecasted-100% spend thresholds.

## What it creates

| Resource | Description |
|---|---|
| **SNS Topic** | `aws-cost-alert-topic` — receives all budget alerts |
| **Email subscription** | Your email via SNS (requires one-time confirmation) |
| **Lambda function** | `aws-cost-alert-slack-forwarder` — forwards SNS → Slack |
| **IAM Role** | `aws-cost-alert-lambda-role` — minimal execution role for Lambda |
| **AWS Budget** | Monthly cost budget with 4 alert thresholds |

## Prerequisites

```bash
pip install boto3
```

Your AWS credentials must be configured with permissions for:
- `budgets:CreateBudget`, `budgets:DeleteBudget`
- `sns:CreateTopic`, `sns:Subscribe`
- `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:AddPermission`
- `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:GetRole`
- `sts:GetCallerIdentity`

## Usage

```bash
python setup_cost_alerts.py \
  --budget 200 \
  --email you@example.com \
  --slack-webhook https://hooks.slack.com/services/XXX/YYY/ZZZ
```

### All options

| Flag | Required | Description |
|---|---|---|
| `--budget` | ✅ | Monthly budget in USD (e.g. `200`) |
| `--email` | ✅ | Email address to receive alerts |
| `--slack-webhook` | ✅ | Slack incoming webhook URL |
| `--budget-name` | ❌ | Custom name for the budget (default: `MonthlyAWSBudget`) |
| `--profile` | ❌ | AWS CLI profile to use |
| `--dry-run` | ❌ | Preview changes without creating anything |

## Example

```bash
# Dry run first to preview
python setup_cost_alerts.py \
  --budget 150 \
  --email alerts@mycompany.com \
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx \
  --dry-run

# Then apply for real
python setup_cost_alerts.py \
  --budget 150 \
  --email alerts@mycompany.com \
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx
```

## Alert thresholds

| Threshold | Type | When triggered |
|---|---|---|
| 50% | Actual spend | You've used half your budget |
| 80% | Actual spend | Approaching budget limit |
| 100% | Actual spend | Budget exceeded |
| 100% | Forecasted | AWS predicts you'll exceed budget by month-end |

## After running

1. **Confirm your email** — AWS SNS sends a confirmation email; click the link.
2. **Test Slack** — You can publish a test message to the SNS topic from the AWS Console.
3. **View the budget** — AWS Console → Billing → Budgets.

## Getting a Slack Webhook URL

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App**
2. Choose **Incoming Webhooks** → toggle on → **Add New Webhook to Workspace**
3. Pick a channel → copy the webhook URL.