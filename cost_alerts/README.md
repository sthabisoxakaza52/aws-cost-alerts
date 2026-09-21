# `cost_alerts` Package

This directory contains the core Python source code and application package for AWS Cost Alerts.

## Architecture & Modules

| Module | Responsibility | Key Functions / Classes |
|---|---|---|
| [`__init__.py`](__init__.py) | Package initialization | Package metadata and exports. |
| [`aws_clients.py`](aws_clients.py) | AWS Session & Authentication | `get_session()`, `get_account_id()` |
| [`budget.py`](budget.py) | AWS Budgets Provisioning | `create_or_update_budget()`, `describe_budget()` |
| [`cli.py`](cli.py) | CLI Interface & Orchestration | `parse_args()`, `validate_args()`, `run_dry_run()`, `main()` |
| [`config.py`](config.py) | System Constants & Configuration | Default budget names, SNS topics, Lambda roles, and thresholds. |
| [`dashboard.html`](dashboard.html) | Interactive Monitoring Web UI | Self-contained HTML/CSS/JS cost monitoring dashboard. |
| [`dashboard.py`](dashboard.py) | Dashboard Utilities & Cloud Deployers | `launch_dashboard()`, `deploy_dashboard_to_s3()`, `deploy_dashboard_to_cloudfront()` |
| [`lambda_fn.py`](lambda_fn.py) | Slack Forwarder & IAM Management | `create_or_update_lambda()`, `create_lambda_role()`, `build_lambda_zip()` |
| [`notifications.py`](notifications.py) | Spend Threshold Calculations | `build_notifications()`, `calculate_threshold_amounts()` |
| [`sns.py`](sns.py) | SNS Topic & Email Subscriptions | `create_sns_topic()`, `subscribe_email()` |
| [`teardown.py`](teardown.py) | Automated Resource Destruction | `destroy_resources()` |

## Testing

Unit tests for each of these modules reside under the [`tests/`](../tests/) directory with 1:1 test coverage.
