"""Tests for teardown module."""

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from cost_alerts.teardown import teardown_resources


class TestTeardownResources:
    def test_teardown_all_resources_success(self):
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
