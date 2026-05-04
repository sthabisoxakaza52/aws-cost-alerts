from unittest.mock import Mock
from setup_cost_alerts import create_sns_topic

def test_create_sns_topic():
    session = Mock()
    sns = Mock()

    session.client.return_value = sns

    sns.create_topic.return_value = {
        "TopicArn": "arn:aws:sns:us-east-1:123:test"
    }

    result = create_sns_topic(session, "test-topic", "test@email.com")

    assert result == "arn:aws:sns:us-east-1:123:test"
    sns.subscribe.assert_called_once()