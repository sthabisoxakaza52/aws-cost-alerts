DEFAULT_REGION = "us-east-1"
SUPPORTED_REGIONS = ["us-east-1", "us-west-1", "us-west-2"]

DEFAULT_BUDGET_NAME = "MonthlyAWSBudget"

ALERT_THRESHOLDS = [
    {"percentage": 50, "type": "PERCENTAGE", "comparison": "GREATER_THAN"},
    {"percentage": 80, "type": "PERCENTAGE", "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "PERCENTAGE", "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "FORECASTED_PERCENTAGE", "comparison": "GREATER_THAN"},
]

CURRENCY_RATES = {
    "USD": 1,
    "ZAR": 18.50,
    "EUR": 21.00,
    "GBP": 0.79,
}