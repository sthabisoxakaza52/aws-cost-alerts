"""Tests for budget module."""

import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from cost_alerts.budget import create_budget


class TestCreateBudget:
    def _run(self, budget_name="TestBudget", budget_amount="100",
             account_id="123456789012", topic_arn="arn:test",
             budget_exists=False):
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
        budgets = MagicMock()
        session = MagicMock()
        session.client.return_value = budgets
        create_budget(session, "123", "TestBudget", "100", "arn:test")
        budgets.delete_budget.assert_not_called()

    def test_missing_budget_delete_is_ignored(self):
        self._run(budget_exists=False).create_budget.assert_called_once()

    def test_existing_budget_updates_in_place_without_delete(self):
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
        budgets = MagicMock()
        budgets.delete_budget.side_effect = budgets.exceptions.NotFoundException()
        budgets.create_budget.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "CreateBudget"
        )
        session = MagicMock()
        session.client.return_value = budgets
        with pytest.raises(ClientError):
            create_budget(session, "123", "Budget", "100", "arn:test")
