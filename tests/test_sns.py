"""Tests for SNS module."""

import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from cost_alerts.sns import create_sns_topic


class TestCreateSnsTopic:
    TOPIC_ARN = "arn:aws:sns:us-east-1:123:test"

    def _run(self, topic_name="test-topic", email="test@example.com"):
        sns = MagicMock()
        sns.create_topic.return_value = {"TopicArn": self.TOPIC_ARN}
        session = MagicMock()
        session.client.return_value = sns
        return create_sns_topic(session, topic_name, email), sns

    def test_returns_topic_arn(self):
        result, _ = self._run()
        assert result == self.TOPIC_ARN

    def test_create_topic_called_with_correct_name(self):
        _, sns = self._run(topic_name="my-topic")
        sns.create_topic.assert_called_once_with(Name="my-topic")

    def test_subscribe_called_with_correct_email(self):
        _, sns = self._run(email="alerts@company.com")
        sns.subscribe.assert_called_once_with(
            TopicArn=self.TOPIC_ARN,
            Protocol="email",
            Endpoint="alerts@company.com",
        )

    def test_subscribe_called_once(self):
        _, sns = self._run()
        assert sns.subscribe.call_count == 1

    def test_propagates_client_error(self):
        sns = MagicMock()
        sns.create_topic.side_effect = ClientError(
            {"Error": {"Code": "AuthFailure", "Message": "denied"}}, "CreateTopic"
        )
        session = MagicMock()
        session.client.return_value = sns
        with pytest.raises(ClientError):
            create_sns_topic(session, "topic", "x@y.com")
