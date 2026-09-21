"""Tests for Lambda Slack forwarder module."""

import pytest
from unittest.mock import MagicMock, patch
from cost_alerts.lambda_fn import (
    create_slack_lambda,
    wait_for_iam_role,
    build_lambda_code,
)


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
        iam, lam, sns = self._make_clients()
        lam.add_permission.side_effect = lam.exceptions.ResourceConflictException()
        session = MagicMock()
        session.client.side_effect = lambda svc, **kw: {"iam": iam, "lambda": lam, "sns": sns}[svc]
        with patch("time.sleep"):
            create_slack_lambda(session, "https://hooks.slack.com/x", self.TOPIC_ARN)

    def test_lambda_code_does_not_embed_webhook_url(self):
        code = build_lambda_code("https://hooks.slack.com/my-webhook")
        assert "https://hooks.slack.com/my-webhook" not in code
        assert "os.environ.get(\"SLACK_WEBHOOK\")" in code

    def test_lambda_code_has_handler(self):
        assert "def handler(event, context):" in build_lambda_code("https://x.com")
