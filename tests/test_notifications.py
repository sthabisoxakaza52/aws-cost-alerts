from setup_cost_alerts import build_notifications

def test_build_notifications():
    topic_arn = "arn:aws:sns:us-east-1:123:test-topic"

    notifications = build_notifications(topic_arn)

    # Should have 4 alert rules
    assert len(notifications) == 4

    # All should point to same SNS topic
    for n in notifications:
        assert n["Subscribers"][0]["Address"] == topic_arn
        assert n["Notification"]["ThresholdType"] == "PERCENTAGE"