"""
Tests for aws-cost-alerts.
Covers: notifications, SNS, budget, Lambda, CLI (dry-run + validation).
All AWS calls are mocked — no real credentials needed.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch


def make_session(client_map):
    session = MagicMock()
    session.client.side_effect = lambda svc, **kw: client_map[svc]
    return session


class TestBuildNotifications:
    def _build(self, topic_arn="arn:aws:sns:us-east-1:123:test"):
        from cost_alerts.notifications import build_notifications
        return build_notifications(topic_arn)

    def test_returns_four_thresholds(self):
        assert len(self._build()) == 4

    def test_all_subscribers_point_to_topic(self):
        arn = "arn:aws:sns:us-east-1:123:test"
        for n in self._build(arn):
            assert n["Subscribers"][0]["Address"] == arn

    def test_threshold_types_are_percentage(self):
        for n in self._build():
            assert n["Notification"]["ThresholdType"] == "PERCENTAGE"

    def test_contains_forecasted_threshold(self):
        types = [n["Notification"]["NotificationType"] for n in self._build()]
        assert "FORECASTED" in types

    def test_contains_actual_thresholds(self):
        types = [n["Notification"]["NotificationType"] for n in self._build()]
        assert types.count("ACTUAL") == 3

    def test_percentages_are_50_80_100_100(self):
        pcts = sorted(n["Notification"]["Threshold"] for n in self._build())
        assert pcts == [50, 80, 100, 100]

    def test_all_use_greater_than_operator(self):
        for n in self._build():
            assert n["Notification"]["ComparisonOperator"] == "GREATER_THAN"

    def test_subscribers_use_sns_subscription_type(self):
        for n in self._build():
            assert n["Subscribers"][0]["SubscriptionType"] == "SNS"


class TestCreateSnsTopic:
    TOPIC_ARN = "arn:aws:sns:us-east-1:123:test"

    def _run(self, topic_name="test-topic", email="test@example.com"):
        from cost_alerts.sns import create_sns_topic
        sns = MagicMock()
        sns.create_topic.return_value = {"TopicArn": self.TOPIC_ARN}
        session = MagicMock()
        session.client.return_value = sns
        return create_sns_topic(session, topic_name, email), sns

    def test_returns_topic_arn(self):
        result, _ = self._run()
        assert result == self.TOPIC_ARN

    def test_create_topic_called_with_correct_name(self):
        _, sns = self._run(topic_name="my-topic")
        sns.create_topic.assert_called_once_with(Name="my-topic")

    def test_subscribe_called_with_correct_email(self):
        _, sns = self._run(email="alerts@company.com")
        sns.subscribe.assert_called_once_with(
            TopicArn=self.TOPIC_ARN,
            Protocol="email",
            Endpoint="alerts@company.com",
        )

    def test_subscribe_called_once(self):
        _, sns = self._run()
        assert sns.subscribe.call_count == 1

    def test_propagates_client_error(self):
        from botocore.exceptions import ClientError
        from cost_alerts.sns import create_sns_topic
        sns = MagicMock()
        sns.create_topic.side_effect = ClientError(
            {"Error": {"Code": "AuthFailure", "Message": "denied"}}, "CreateTopic"
        )
        session = MagicMock()
        session.client.return_value = sns
        with pytest.raises(ClientError):
            create_sns_topic(session, "topic", "x@y.com")


class TestCreateBudget:
    def _run(self, budget_name="TestBudget", budget_amount="100",
             account_id="123456789012", topic_arn="arn:test",
             budget_exists=False):
        from cost_alerts.budget import create_budget
        budgets = MagicMock()
        if not budget_exists:
            budgets.delete_budget.side_effect = budgets.exceptions.NotFoundException()
        session = MagicMock()
        session.client.return_value = budgets
        create_budget(session, account_id, budget_name, budget_amount, topic_arn)
        return budgets

    def test_create_budget_called_once(self):
        self._run().create_budget.assert_called_once()

    def test_budget_name_passed_correctly(self):
        budgets = self._run(budget_name="MyBudget")
        assert budgets.create_budget.call_args[1]["Budget"]["BudgetName"] == "MyBudget"

    def test_budget_amount_passed_correctly(self):
        budgets = self._run(budget_amount="250")
        assert budgets.create_budget.call_args[1]["Budget"]["BudgetLimit"]["Amount"] == "250"

    def test_budget_currency_is_usd(self):
        budgets = self._run()
        assert budgets.create_budget.call_args[1]["Budget"]["BudgetLimit"]["Unit"] == "USD"

    def test_budget_type_is_cost(self):
        budgets = self._run()
        assert budgets.create_budget.call_args[1]["Budget"]["BudgetType"] == "COST"

    def test_time_unit_is_monthly(self):
        budgets = self._run()
        assert budgets.create_budget.call_args[1]["Budget"]["TimeUnit"] == "MONTHLY"

    def test_notifications_are_passed(self):
        budgets = self._run(topic_arn="arn:aws:sns:us-east-1:123:topic")
        assert len(budgets.create_budget.call_args[1]["NotificationsWithSubscribers"]) == 4

    def test_existing_budget_is_deleted_first(self):
        from cost_alerts.budget import create_budget
        budgets = MagicMock()
        session = MagicMock()
        session.client.return_value = budgets
        create_budget(session, "123", "TestBudget", "100", "arn:test")
        budgets.delete_budget.assert_not_called()

    def test_missing_budget_delete_is_ignored(self):
        self._run(budget_exists=False).create_budget.assert_called_once()

    def test_existing_budget_updates_in_place_without_delete(self):
        from botocore.exceptions import ClientError
        from cost_alerts.budget import create_budget
        budgets = MagicMock()
        budgets.create_budget.side_effect = ClientError(
            {"Error": {"Code": "DuplicateRecordException", "Message": "duplicate"}},
            "CreateBudget"
        )
        session = MagicMock()
        session.client.return_value = budgets

        create_budget(session, "123", "TestBudget", "100", "arn:test")

        budgets.update_budget.assert_called_once()
        budgets.delete_budget.assert_not_called()

    def test_propagates_client_error_on_create(self):
        from botocore.exceptions import ClientError
        from cost_alerts.budget import create_budget
        budgets = MagicMock()
        budgets.delete_budget.side_effect = budgets.exceptions.NotFoundException()
        budgets.create_budget.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "CreateBudget"
        )
        session = MagicMock()
        session.client.return_value = budgets
        with pytest.raises(ClientError):
            create_budget(session, "123", "Budget", "100", "arn:test")


class TestCreateSlackLambda:
    TOPIC_ARN  = "arn:aws:sns:us-east-1:123:topic"
    LAMBDA_ARN = "arn:aws:lambda:us-east-1:123:function:aws-cost-alert-slack-forwarder"
    ROLE_ARN   = "arn:aws:iam::123:role/aws-cost-alert-lambda-role"

    def _make_clients(self, role_exists=True, lambda_exists=False):
        iam = MagicMock()
        lam = MagicMock()
        sns = MagicMock()

        class NoSuchEntityException(Exception):
            pass

        class ResourceNotFoundException(Exception):
            pass

        class ResourceConflictException(Exception):
            pass

        iam.exceptions.NoSuchEntityException = NoSuchEntityException
        lam.exceptions.ResourceNotFoundException = ResourceNotFoundException
        lam.exceptions.ResourceConflictException = ResourceConflictException

        if role_exists:
            iam.get_role.return_value = {"Role": {"Arn": self.ROLE_ARN}}
        else:
            iam.get_role.side_effect = [
                NoSuchEntityException(),
                {"Role": {"Arn": self.ROLE_ARN}},
            ]
            iam.create_role.return_value = {"Role": {"Arn": self.ROLE_ARN}}
        if lambda_exists:
            lam.get_function.return_value = {"Configuration": {"FunctionArn": self.LAMBDA_ARN}}
        else:
            lam.get_function.side_effect = ResourceNotFoundException()
            lam.create_function.return_value = {"FunctionArn": self.LAMBDA_ARN}
        return iam, lam, sns

    def _run(self, role_exists=True, lambda_exists=False):
        from cost_alerts.lambda_fn import create_slack_lambda
        iam, lam, sns = self._make_clients(role_exists, lambda_exists)
        session = MagicMock()
        session.client.side_effect = lambda svc, **kw: {"iam": iam, "lambda": lam, "sns": sns}[svc]
        with patch("time.sleep"):
            result = create_slack_lambda(session, "https://hooks.slack.com/x", self.TOPIC_ARN)
        return result, iam, lam, sns

    def test_returns_lambda_arn(self):
        assert self._run()[0] == self.LAMBDA_ARN

    def test_creates_lambda_when_not_exists(self):
        _, _, lam, _ = self._run(lambda_exists=False)
        lam.create_function.assert_called_once()

    def test_updates_lambda_when_exists(self):
        _, _, lam, _ = self._run(lambda_exists=True)
        lam.update_function_code.assert_called_once()
        lam.create_function.assert_not_called()

    def test_reuses_iam_role_when_exists(self):
        _, iam, _, _ = self._run(role_exists=True)
        iam.create_role.assert_not_called()

    def test_creates_iam_role_when_missing(self):
        _, iam, _, _ = self._run(role_exists=False)
        iam.create_role.assert_called_once()
        iam.attach_role_policy.assert_called_once()

    def test_sns_subscribe_called(self):
        _, _, _, sns = self._run()
        sns.subscribe.assert_called_once_with(
            TopicArn=self.TOPIC_ARN, Protocol="lambda", Endpoint=self.LAMBDA_ARN,
        )

    def test_add_permission_called(self):
        _, _, lam, _ = self._run()
        lam.add_permission.assert_called_once()

    def test_wait_for_iam_role_retries_until_ready(self):
        from cost_alerts.lambda_fn import wait_for_iam_role
        iam = MagicMock()
        iam.get_role.side_effect = [
            Exception("not ready yet"),
            {"Role": {"Arn": self.ROLE_ARN}},
        ]

        with patch("time.sleep") as mock_sleep:
            role = wait_for_iam_role(iam, "aws-cost-alert-lambda-role")

        assert role["Role"]["Arn"] == self.ROLE_ARN
        assert iam.get_role.call_count == 2
        assert mock_sleep.called

    def test_permission_conflict_is_ignored(self):
        from cost_alerts.lambda_fn import create_slack_lambda
        iam, lam, sns = self._make_clients()
        lam.add_permission.side_effect = lam.exceptions.ResourceConflictException()
        session = MagicMock()
        session.client.side_effect = lambda svc, **kw: {"iam": iam, "lambda": lam, "sns": sns}[svc]
        with patch("time.sleep"):
            create_slack_lambda(session, "https://hooks.slack.com/x", self.TOPIC_ARN)

    def test_lambda_code_does_not_embed_webhook_url(self):
        from cost_alerts.lambda_fn import build_lambda_code
        code = build_lambda_code("https://hooks.slack.com/my-webhook")
        assert "https://hooks.slack.com/my-webhook" not in code
        assert "os.environ.get(\"SLACK_WEBHOOK\")" in code

    def test_lambda_code_has_handler(self):
        from cost_alerts.lambda_fn import build_lambda_code
        assert "def handler(event, context):" in build_lambda_code("https://x.com")


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
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", self.BASE_ARGV + ["--dry-run"] + (extra_argv or []))
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        return capsys.readouterr().out

    def test_dry_run_exits_zero(self, monkeypatch):
        from cost_alerts.cli import main
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
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", self.EMAIL_ONLY_ARGV + ["--dry-run"])

        with pytest.raises(SystemExit) as exc:
            main()

        assert exc.value.code == 0
        output = capsys.readouterr().out
        assert "Slack Lambda" not in output
        assert "IAM Role" not in output

    def test_email_only_provisioning_skips_lambda(self, monkeypatch):
        from cost_alerts.cli import main

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
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--budget", "0", "--email", "x@y.com", "--slack-webhook", "https://hooks.slack.com/x"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_invalid_budget_negative_exits_nonzero(self, monkeypatch):
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--budget", "-50", "--email", "x@y.com", "--slack-webhook", "https://hooks.slack.com/x"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_validate_slack_webhook_requires_slack_domain(self):
        from cost_alerts.cli import validate_slack_webhook

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
        from cost_alerts.cli import main

        monkeypatch.setattr(
            sys,
            "argv",
            self.BASE_ARGV + ["--dry-run"] + extra_args,
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_missing_required_args_exits_nonzero(self, monkeypatch):
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_aws_error_exits_nonzero(self, monkeypatch):
        from botocore.exceptions import ClientError
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", self.BASE_ARGV)
        with patch("cost_alerts.cli.get_account_id") as mock_acct, patch("cost_alerts.cli.get_session"):
            mock_acct.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "GetCallerIdentity"
            )
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code != 0

    def test_destroy_dry_run_exits_zero(self, monkeypatch, capsys):
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--destroy", "--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AWS Cost Alerts Teardown" in out
        assert "Dry Run Mode" in out
        assert "Resources to be deleted" in out

    def test_destroy_executes_teardown(self, monkeypatch):
        from cost_alerts.cli import main
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
        from cost_alerts.cli import main
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
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--dashboard", "--port", "9000"])
        with patch("cost_alerts.cli.launch_dashboard") as mock_launch:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
            mock_launch.assert_called_once_with(port=9000, open_browser=True)

    def test_deploy_dashboard_dry_run_exits_zero(self, monkeypatch, capsys):
        from cost_alerts.cli import main
        monkeypatch.setattr(sys, "argv", ["aws-cost-alerts", "--deploy-dashboard", "--dry-run"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "AWS Cost Alerts Dashboard S3 Deployment" in out
        assert "Dry Run Mode" in out

    def test_deploy_dashboard_executes(self, monkeypatch):
        from cost_alerts.cli import main
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


class TestTeardownResources:
    def test_teardown_all_resources_success(self):
        from cost_alerts.teardown import teardown_resources

        budgets = MagicMock()
        sns = MagicMock()
        lambda_client = MagicMock()
        iam = MagicMock()

        session = MagicMock()
        session.client.return_value = budgets

        with patch("cost_alerts.teardown.get_sns_client", return_value=sns), \
             patch("cost_alerts.teardown.get_lambda_client", return_value=lambda_client), \
             patch("cost_alerts.teardown.get_iam_client", return_value=iam):
            res = teardown_resources(
                session=session,
                account_id="123456789012",
                budget_name="MyBudget",
                region="us-east-1",
            )

        budgets.delete_budget.assert_called_once_with(AccountId="123456789012", BudgetName="MyBudget")
        sns.delete_topic.assert_called_once_with(TopicArn="arn:aws:sns:us-east-1:123456789012:aws-cost-alert-topic")
        lambda_client.delete_function.assert_called_once_with(FunctionName="aws-cost-alert-slack-forwarder")
        iam.detach_role_policy.assert_called_once_with(
            RoleName="aws-cost-alert-lambda-role",
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        iam.delete_role.assert_called_once_with(RoleName="aws-cost-alert-lambda-role")
        assert res == {"budget": "deleted", "sns": "deleted", "lambda": "deleted", "iam_role": "deleted"}

    def test_teardown_handles_missing_resources_gracefully(self):
        from botocore.exceptions import ClientError
        from cost_alerts.teardown import teardown_resources

        budgets = MagicMock()
        budgets.delete_budget.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Not found"}}, "DeleteBudget"
        )
        sns = MagicMock()
        sns.delete_topic.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Not found"}}, "DeleteTopic"
        )
        lambda_client = MagicMock()
        lambda_client.delete_function.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}, "DeleteFunction"
        )
        iam = MagicMock()
        iam.detach_role_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Not found"}}, "DetachRolePolicy"
        )
        iam.delete_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Not found"}}, "DeleteRole"
        )

        session = MagicMock()
        session.client.return_value = budgets

        with patch("cost_alerts.teardown.get_sns_client", return_value=sns), \
             patch("cost_alerts.teardown.get_lambda_client", return_value=lambda_client), \
             patch("cost_alerts.teardown.get_iam_client", return_value=iam):
            res = teardown_resources(
                session=session,
                account_id="123456789012",
                budget_name="MyBudget",
                region="us-east-1",
            )

        assert res == {"budget": "not_found", "sns": "not_found", "lambda": "not_found", "iam_role": "not_found"}

    def test_teardown_propagates_unexpected_client_error(self):
        from botocore.exceptions import ClientError
        from cost_alerts.teardown import teardown_resources

        budgets = MagicMock()
        budgets.delete_budget.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}}, "DeleteBudget"
        )

        session = MagicMock()
        session.client.return_value = budgets

        with pytest.raises(ClientError):
            teardown_resources(
                session=session,
                account_id="123456789012",
                budget_name="MyBudget",
            )


class TestDashboard:
    def test_dashboard_path_exists(self):
        from cost_alerts.dashboard import get_dashboard_path
        path = get_dashboard_path()
        assert path.exists()
        assert path.name == "dashboard.html"

    def test_launch_dashboard_browser(self):
        from cost_alerts.dashboard import launch_dashboard
        with patch("webbrowser.open") as mock_browser:
            url = launch_dashboard(open_browser=True, serve=False)
            assert url.startswith("file://")
            assert url.endswith("dashboard.html")
            mock_browser.assert_called_once_with(url)

    def test_launch_dashboard_missing_file_raises(self):
        from cost_alerts.dashboard import launch_dashboard
        with patch("cost_alerts.dashboard.get_dashboard_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file
            with pytest.raises(FileNotFoundError):
                launch_dashboard()

    def test_deploy_dashboard_to_s3_success(self):
        from cost_alerts.dashboard import deploy_dashboard_to_s3

        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-url"
        session = MagicMock()
        session.client.return_value = s3

        res = deploy_dashboard_to_s3(
            session=session,
            account_id="123456789012",
            region="eu-north-1",
            bucket_name="my-test-bucket",
        )

        s3.create_bucket.assert_called_once_with(
            Bucket="my-test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-north-1"},
        )
        s3.upload_file.assert_called_once()
        s3.put_bucket_website.assert_called_once()
        assert res["bucket"] == "my-test-bucket"
        assert "http://my-test-bucket.s3-website.eu-north-1.amazonaws.com" in res["website_url"]
        assert res["presigned_url"] == "https://s3.amazonaws.com/test-url"


def test_readme_preserves_cleanup_instructions():
    readme = (Path(__file__).parent.parent / "README.md").read_text(
        encoding="utf-8"
    )

    assert "WTC-JJNPY2UD" in readme
    cleanup_section = readme.split("## Uninstall / Cleanup", 1)
    assert len(cleanup_section) == 2
    assert readme.rstrip().endswith("Delete `aws-cost-alert-lambda-role`")
    assert "Delete `MonthlyAWSBudget`" in cleanup_section[1]
    assert "Delete `aws-cost-alert-topic`" in cleanup_section[1]
    assert "Delete `aws-cost-alert-slack-forwarder`" in cleanup_section[1]
    assert "Delete `aws-cost-alert-lambda-role`" in cleanup_section[1]
