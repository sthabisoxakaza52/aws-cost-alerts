from unittest.mock import Mock
from setup_cost_alerts import create_budget

def test_create_budget():
    session = Mock()
    budgets = Mock()

    session.client.return_value = budgets

    # simulate "budget does not exist yet"
    budgets.delete_budget.side_effect = Exception("NotFound")

    create_budget(
        session,
        account_id="123456789012",
        budget_name="TestBudget",
        budget_amount="100",
        topic_arn="arn:test"
    )

    budgets.create_budget.assert_called_once()