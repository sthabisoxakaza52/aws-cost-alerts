"""Tests for CLI module."""

import sys
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from cost_alerts.cli import main, validate_slack_webhook


class TestCli:
    BASE_ARGV = [
        "aws-cost-alerts",
        "--budget", "150",
        "--email", "test@example.com",
        "--slack-webhook", "https://hooks.slack.com/test",
    ]
    EMAIL_ONLY_ARGV = [
        "aws-cost-alerts",
        "--budget", "150",
        "--email", "test@example.com",
    ]

    def _dry_run(self, monkeypatch, capsys, extra_argv=None):
        monkeypatch.setattr(sys, "argv", self.BASE_ARGV + ["--dry-run"] + (extra_argv or []))
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        return capsys.readouterr().out

    def test_dry_run_exits_zero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", self.BASE_ARGV + ["--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_dry_run_output_contains_dry_run(self, monkeypatch, capsys):
        out = self._dry_run(monkeypatch, capsys)
        assert "Dry Run" in out or "DRY RUN" in out

    def test_dry_run_confirms_no_aws_changes(self, monkeypatch, capsys):
        output = self._dry_run(monkeypatch, capsys)
        assert "No AWS resources will be modified" in output

    def test_dry_run_shows_budget_amount(self, monkeypatch, capsys):
        assert "150" in self._dry_run(monkeypatch, capsys)

    def test_dry_run_shows_email(self, monkeypatch, capsys):
        assert "test@example.com" in self._dry_run(monkeypatch, capsys)

    def test_dry_run_shows_selected_region(self, monkeypatch, capsys):
        output = self._dry_run(
            monkeypatch,
            capsys,
            ["--region", "us-west-2"],
        )
        assert "AWS Region    : us-west-2" in output

    def test_email_only_dry_run_omits_slack_resources(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", self.EMAIL_ONLY_ARGV + ["--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        output = capsys.readouterr().out
        assert "Slack Lambda" not in output
        assert "IAM Role" not in output

    def test_email_only_provisioning_skips_lambda(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", self.EMAIL_ONLY_ARGV)
        session = MagicMock()

        with (
            patch("cost_alerts.cli.get_session", return_value=session),
            patch("cost_alerts.cli.get_account_id", return_value="123"),
            patch("cost_alerts.cli.create_sns_topic", return_value="arn:test"),
            patch("cost_alerts.cli.create_budget") as create_budget,
            patch("cost_alerts.cli.create_slack_lambda") as create_slack_lambda,
        ):
            main()

        create_budget.assert_called_once()
        create_slack_lambda.assert_not_called()

    def test_invalid_budget_zero_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--budget", "0", "--email", "x@y.com", "--slack-webhook", "https://hooks.slack.com/x"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_invalid_budget_negative_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--budget", "-50", "--email", "x@y.com", "--slack-webhook", "https://hooks.slack.com/x"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_validate_slack_webhook_requires_slack_domain(self):
        with pytest.raises(ValueError):
            validate_slack_webhook("https://example.com/not-a-slack-webhook")

    @pytest.mark.parametrize(
        "extra_args",
        [
            ["--region", "eu-west-1"],
            ["--email", "invalid-email"],
            ["--budget-name", "   "],
            ["--slack-webhook", "http://hooks.slack.com/test"],
        ],
    )
    def test_invalid_configuration_exits_nonzero(self, monkeypatch, extra_args):
        monkeypatch.setattr(
            sys,
            "argv",
            self.BASE_ARGV + ["--dry-run"] + extra_args,
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_missing_required_args_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_aws_error_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", self.BASE_ARGV)
        with patch("cost_alerts.cli.get_account_id") as mock_acct, patch("cost_alerts.cli.get_session"):
            mock_acct.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "GetCallerIdentity"
            )
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code != 0

    def test_destroy_dry_run_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--destroy", "--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AWS Cost Alerts Teardown" in out
        assert "Dry Run Mode" in out
        assert "Resources to be deleted" in out

    def test_destroy_executes_teardown(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--destroy", "--budget-name", "CustomBudget"])
        with patch("cost_alerts.cli.get_session"), \
             patch("cost_alerts.cli.get_account_id", return_value="123456789012"), \
             patch("cost_alerts.cli.teardown_resources") as mock_teardown:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
            mock_teardown.assert_called_once_with(
                session=mock_teardown.call_args[1]["session"],
                account_id="123456789012",
                budget_name="CustomBudget",
                region="us-east-1",
            )

    def test_dashboard_dry_run_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--dashboard", "--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AWS Cost Alerts Dashboard" in out
        assert "Dry Run Mode" in out
        assert "Dashboard File" in out
        assert "Browser launch suppressed in dry-run mode." in out

    def test_dashboard_executes_launch(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--dashboard", "--port", "9000"])
        with patch("cost_alerts.cli.launch_dashboard") as mock_launch:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
            mock_launch.assert_called_once_with(port=9000, open_browser=True)

    def test_deploy_dashboard_dry_run_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--deploy-dashboard", "--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AWS Cost Alerts Dashboard S3 Deployment" in out
        assert "Dry Run Mode" in out

    def test_deploy_dashboard_executes(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--deploy-dashboard", "--region", "eu-north-1"])
        with patch("cost_alerts.cli.get_session"), \
             patch("cost_alerts.cli.get_account_id", return_value="123456789012"), \
             patch("cost_alerts.cli.deploy_dashboard_to_s3") as mock_deploy:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
            mock_deploy.assert_called_once_with(
                session=mock_deploy.call_args[1]["session"],
                account_id="123456789012",
                region="eu-north-1"
            )

    def test_deploy_cloudfront_dry_run_exits_zero(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--deploy-cloudfront", "--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AWS Cost Alerts Dashboard CloudFront Deployment" in out
        assert "Dry Run Mode" in out

    def test_deploy_cloudfront_executes(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--deploy-cloudfront", "--region", "eu-north-1"])
        with patch("cost_alerts.cli.get_session"), \
             patch("cost_alerts.cli.get_account_id", return_value="123456789012"), \
             patch("cost_alerts.cli.deploy_dashboard_to_cloudfront") as mock_deploy:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
            mock_deploy.assert_called_once_with(
                session=mock_deploy.call_args[1]["session"],
                region="eu-north-1"
            )
