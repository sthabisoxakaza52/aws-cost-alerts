"""Tests for notifications module."""

from cost_alerts.notifications import build_notifications


class TestBuildNotifications:
    def _build(self, topic_arn="arn:aws:sns:us-east-1:123:test"):
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
