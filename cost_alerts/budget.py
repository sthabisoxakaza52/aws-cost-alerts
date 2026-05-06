# cost_alerts/budget.py

from botocore.exceptions import ClientError
from .config import DEFAULT_REGION
from .notifications import build_notifications


def create_budget(session, account_id, budget_name, budget_amount, topic_arn):
    budgets = session.client("budgets", region_name=DEFAULT_REGION)

    budget = {
        "BudgetName": budget_name,
        "BudgetType": "COST",
        "TimeUnit": "MONTHLY",
        "BudgetLimit": {
            "Amount": str(budget_amount),
            "Unit": "USD"
        },
        "CostTypes": {
            "IncludeTax": True,
            "IncludeSubscription": True,
            "UseBlended": False,
            "IncludeRefund": False,
            "IncludeCredit": False,
            "IncludeUpfront": True,
            "IncludeRecurring": True,
            "IncludeOtherSubscription": True,
            "IncludeSupport": True,
            "IncludeDiscount": True,
            "UseAmortized": False,
        }
    }

    notifications = build_notifications(topic_arn)

    try:
        # Delete existing budget if it exists
        try:
            budgets.delete_budget(
                AccountId=account_id,
                BudgetName=budget_name
            )
            print(f"Deleted existing budget '{budget_name}'")
        except budgets.exceptions.NotFoundException:
            pass

        print(f"Creating budget '{budget_name}'...")
        budgets.create_budget(
            AccountId=account_id,
            Budget=budget,
            NotificationsWithSubscribers=notifications,
        )

    except ClientError as e:
        print(f"Error creating budget: {e}")
        raise