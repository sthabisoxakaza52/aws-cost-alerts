# AWS Cost Alert Setup

A Python/Boto3 script that provisions AWS Budget alerts with **email (SNS)** and **optional Slack** notifications at 50%, 80%, 100%, and forecasted-100% spend thresholds — with a polished terminal UI and live progress spinners.

---

## What it creates

| Resource | Name | Description |
|---|---|---|
| **SNS Topic** | `aws-cost-alert-topic` | Receives all budget alert events |
| **Email subscription** | _(your email)_ | Requires one-time confirmation click |
| **Lambda function** | `aws-cost-alert-slack-forwarder` | Forwards SNS → Slack _(optional)_ |
| **IAM Role** | `aws-cost-alert-lambda-role` | Minimal execution role for Lambda |
| **AWS Budget** | `MonthlyAWSBudget` | Monthly cost budget with 4 alert thresholds |

---

## Prerequisites

### 1 — Python 3.8+

| OS | Check / Install |
|---|---|
| **Windows** | [python.org/downloads](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install |
| **macOS** | `python3 --version` — install via [python.org](https://www.python.org/downloads/) or `brew install python` |
| **Linux** | `python3 --version` — install via `sudo apt install python3` / `sudo dnf install python3` |

### 2 — Install dependencies

```bash
pip install boto3
```

> On some systems use `pip3` instead of `pip`.

### 3 — AWS credentials configured

Run `aws configure` (requires the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)), or set environment variables:

```bash
# macOS / Linux / Git Bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

```powershell
# Windows PowerShell
$env:AWS_ACCESS_KEY_ID     = "AKIA..."
$env:AWS_SECRET_ACCESS_KEY = "..."
$env:AWS_DEFAULT_REGION    = "us-east-1"
```

```cmd
REM Windows Command Prompt (CMD)
set AWS_ACCESS_KEY_ID=AKIA...
set AWS_SECRET_ACCESS_KEY=...
set AWS_DEFAULT_REGION=us-east-1
```

The IAM user/role needs these permissions:
- `budgets:CreateBudget`, `budgets:DeleteBudget`
- `sns:CreateTopic`, `sns:Subscribe`
- `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:AddPermission`, `lambda:GetFunction`
- `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:GetRole`
- `sts:GetCallerIdentity`

---

## Usage

### Windows — PowerShell

Use a **backtick (`` ` ``)** for line continuation:

```powershell
python setup_cost_alerts.py `
  --budget 150 `
  --email alerts@mycompany.com `
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx
```

Or all on one line:

```powershell
python setup_cost_alerts.py --budget 150 --email alerts@mycompany.com --slack-webhook https://hooks.slack.com/services/T00/B00/xxx
```

### Windows — Command Prompt (CMD)

Use a **caret (`^`)** for line continuation:

```cmd
python setup_cost_alerts.py ^
  --budget 150 ^
  --email alerts@mycompany.com ^
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx
```

### macOS / Linux / Git Bash / WSL

Use a **backslash (`\`)** for line continuation:

```bash
python3 setup_cost_alerts.py \
  --budget 150 \
  --email alerts@mycompany.com \
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx
```

---

## All options

| Flag | Required | Description |
|---|---|---|
| `--budget` | ✅ | Monthly budget limit in USD (e.g. `150`) |
| `--email` | ✅ | Email address to receive SNS alerts |
| `--slack-webhook` | ❌ | Slack incoming webhook URL — omit to skip Slack setup |
| `--budget-name` | ❌ | Custom name for the budget (default: `MonthlyAWSBudget`) |
| `--profile` | ❌ | AWS CLI named profile to use |
| `--dry-run` | ❌ | Preview what would be created without making any changes |

---

## Example workflow

**Step 1 — Dry run first (safe preview)**

```bash
# macOS / Linux
python3 setup_cost_alerts.py \
  --budget 150 \
  --email alerts@mycompany.com \
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx \
  --dry-run
```

```powershell
# Windows PowerShell
python setup_cost_alerts.py `
  --budget 150 `
  --email alerts@mycompany.com `
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx `
  --dry-run
```

**Step 2 — Apply for real (remove `--dry-run`)**

```bash
python3 setup_cost_alerts.py \
  --budget 150 \
  --email alerts@mycompany.com \
  --slack-webhook https://hooks.slack.com/services/T00/B00/xxx
```

**Email-only setup (no Slack)**

```bash
python3 setup_cost_alerts.py --budget 150 --email alerts@mycompany.com
```

---

## Alert thresholds

| Threshold | Type | Triggered when… |
|---|---|---|
| 50% | Actual spend | You've used half your budget |
| 80% | Actual spend | Approaching the budget limit |
| 100% | Actual spend | Budget has been exceeded |
| 100% | Forecasted | AWS predicts you'll exceed budget by month-end |

---

## After running

1. **Confirm your email** — AWS SNS sends a confirmation email immediately; click the link to activate alerts.
2. **Test Slack** — Publish a test message to the SNS topic from the AWS Console → SNS → Topics.
3. **View the budget** — AWS Console → Billing & Cost Management → Budgets.

---

## Getting a Slack Webhook URL

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Under **Features**, choose **Incoming Webhooks** → toggle **On**
3. Click **Add New Webhook to Workspace** → pick a channel → **Allow**
4. Copy the generated webhook URL and pass it as `--slack-webhook`

---

## Troubleshooting

| Error | Fix |
|---|---|
| `command not found: python` | Use `python3` instead, or ensure Python is on your PATH |
| `ModuleNotFoundError: boto3` | Run `pip install boto3` (or `pip3 install boto3`) |
| `ParserError: Missing expression after unary operator '--'` | You're in PowerShell — use backtick `` ` `` for line continuation, not `\` |
| `NoCredentialsError` | Run `aws configure` or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` |
| `AccessDenied` | Ensure your IAM user has all required permissions listed above |
| `SubscriptionLimitExceeded` | Delete old unused SNS subscriptions in the AWS Console |

---

## Uninstall / Cleanup

To remove all created resources:

1. **Budget** — AWS Console → Billing → Budgets → Delete `MonthlyAWSBudget`
2. **SNS Topic** — AWS Console → SNS → Topics → Delete `aws-cost-alert-topic`
3. **Lambda** — AWS Console → Lambda → Delete `aws-cost-alert-slack-forwarder`
4. **IAM Role** — AWS Console → IAM → Roles → Delete `aws-cost-alert-lambda-role`

   WTC-JJNPY2UD
   
