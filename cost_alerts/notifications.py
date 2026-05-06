# cost_alerts/notifications.py

from .config import ALERT_THRESHOLDS


def build_notifications(topic_arn):
    notifications = []

    for t in ALERT_THRESHOLDS:
        threshold_type = (
            "FORECASTED"
            if t["type"] == "FORECASTED_PERCENTAGE"
            else "ACTUAL"
        )

        notifications.append({
            "Notification": {
                "NotificationType": threshold_type,
                "ComparisonOperator": t["comparison"],
                "Threshold": t["percentage"],
                "ThresholdType": "PERCENTAGE",
                "NotificationState": "ALARM",
            },
            "Subscribers": [
                {"SubscriptionType": "SNS", "Address": topic_arn}
            ]
        })

    return notifications