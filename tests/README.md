# Test Suite

The test suite uses `pytest` and is organized into modular, domain-driven test files corresponding 1:1 with each module in `cost_alerts/`.

## Test Modules

| Test File | Target Component | Coverage |
|---|---|---|
| [`test_budget.py`](test_budget.py) | `cost_alerts.budget` | AWS Budgets creation, updates in place, limits, thresholds, currency. |
| [`test_cli.py`](test_cli.py) | `cost_alerts.cli` | Argument parsing, validation, dry-run previews, destroy, and deploy flags. |
| [`test_dashboard.py`](test_dashboard.py) | `cost_alerts.dashboard` | Local server, browser launch, S3 upload, and CloudFront deployment. |
| [`test_lambda_fn.py`](test_lambda_fn.py) | `cost_alerts.lambda_fn` | Slack Lambda forwarder creation, code builder, IAM role creation, and retry logic. |
| [`test_notifications.py`](test_notifications.py) | `cost_alerts.notifications` | Notification threshold builder (50%, 80%, 100%, and forecasted). |
| [`test_sns.py`](test_sns.py) | `cost_alerts.sns` | SNS topic provisioning and email subscription handling. |
| [`test_teardown.py`](test_teardown.py) | `cost_alerts.teardown` | Automated resource destruction and error resilience. |
| [`test_readme.py`](test_readme.py) | `README.md` | Verification of project code `WTC-JJNPY2UD` and preserved cleanup instructions. |
| [`conftest.py`](conftest.py) | Test Fixtures | Shared mock session helpers and package path resolution. |

## Running Tests

Run all tests:
```bash
pytest -v
```

Run a specific module:
```bash
pytest tests/test_budget.py -v
pytest tests/test_cli.py -v
pytest tests/test_dashboard.py -v
```
