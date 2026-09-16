from botocore.exceptions import ClientError
from .notifications import build_notifications


def create_budget(session, account_id, budget_name, budget_amount, topic_arn):
    budgets = session.client("budgets")

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
        print(f"Creating budget '{budget_name}'...")
        budgets.create_budget(
            AccountId=account_id,
            Budget=budget,
            NotificationsWithSubscribers=notifications,
        )
        return

    except Exception as exc:
        duplicate_exception = (
            isinstance(exc, ClientError)
            and exc.response.get("Error", {}).get("Code") == "DuplicateRecordException"
        )

        exceptions = getattr(budgets, "exceptions", None)
        if not duplicate_exception and exceptions is not None:
            duplicate_error = getattr(exceptions, "DuplicateRecordException", None)
            if isinstance(duplicate_error, type):
                duplicate_exception = isinstance(exc, duplicate_error)

        if not duplicate_exception:
            print(f"Error creating budget: {exc}")
            raise

    print(f"Budget '{budget_name}' already exists. Updating the existing budget...")
    budgets.update_budget(
        AccountId=account_id,
        BudgetName=budget_name,
        NewBudget=budget,
        NotificationsWithSubscribers=notifications,
    )