DEFAULT_REGION = "us-east-1"

DEFAULT_BUDGET_NAME = "MonthlyAWSBudget"

ALERT_THRESHOLDS = [
     {"percentage": 50,  "type": "PERCENTAGE",           "comparison": "GREATER_THAN"},
    {"percentage": 80,  "type": "PERCENTAGE",           "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "PERCENTAGE",           "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "FORECASTED_PERCENTAGE","comparison": "GREATER_THAN"},
]