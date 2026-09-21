"""Tests for dashboard module."""

import pytest
from unittest.mock import MagicMock, patch
from cost_alerts.dashboard import (
    get_dashboard_path,
    launch_dashboard,
    deploy_dashboard_to_s3,
    get_cloudfront_template_path,
    deploy_dashboard_to_cloudfront,
)


class TestDashboard:
    def test_dashboard_path_exists(self):
        path = get_dashboard_path()
        assert path.exists()
        assert path.name == "dashboard.html"

    def test_launch_dashboard_browser(self):
        with patch("webbrowser.open") as mock_browser:
            url = launch_dashboard(open_browser=True, serve=False)
            assert url.startswith("file://")
            assert url.endswith("dashboard.html")
            mock_browser.assert_called_once_with(url)

    def test_launch_dashboard_missing_file_raises(self):
        with patch("cost_alerts.dashboard.get_dashboard_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file
            with pytest.raises(FileNotFoundError):
                launch_dashboard()

    def test_deploy_dashboard_to_s3_success(self):
        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-url"
        session = MagicMock()
        session.client.return_value = s3

        res = deploy_dashboard_to_s3(
            session=session,
            account_id="123456789012",
            region="eu-north-1",
            bucket_name="my-test-bucket",
        )

        s3.create_bucket.assert_called_once_with(
            Bucket="my-test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-north-1"},
        )
        s3.upload_file.assert_called_once()
        s3.put_bucket_website.assert_called_once()
        assert res["bucket"] == "my-test-bucket"
        assert "http://my-test-bucket.s3-website.eu-north-1.amazonaws.com" in res["website_url"]
        assert res["presigned_url"] == "https://s3.amazonaws.com/test-url"

    def test_cloudfront_template_path_exists(self):
        path = get_cloudfront_template_path()
        assert path.exists()
        assert path.name == "cloudfront.yaml"

    def test_deploy_dashboard_to_cloudfront_success(self):
        cf = MagicMock()
        stack_outputs = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "BucketName", "OutputValue": "my-cf-bucket"},
                        {"OutputKey": "DistributionId", "OutputValue": "E12345EXAMPLE"},
                        {"OutputKey": "WebsiteURL", "OutputValue": "https://d123456789.cloudfront.net"},
                    ]
                }
            ]
        }
        cf.describe_stacks.side_effect = [Exception("Stack does not exist"), stack_outputs]
        waiter = MagicMock()
        cf.get_waiter.return_value = waiter

        s3 = MagicMock()
        session = MagicMock()
        session.client.side_effect = lambda svc, **kw: {"cloudformation": cf, "s3": s3}[svc]

        res = deploy_dashboard_to_cloudfront(
            session=session,
            region="eu-north-1",
            stack_name="aws-cost-alerts-cdn",
        )

        assert cf.describe_stacks.call_count == 2
        cf.create_stack.assert_called_once()
        waiter.wait.assert_called_once_with(StackName="aws-cost-alerts-cdn")
        s3.upload_file.assert_called_once()
        assert res["bucket"] == "my-cf-bucket"
        assert res["distribution_id"] == "E12345EXAMPLE"
        assert res["website_url"] == "https://d123456789.cloudfront.net"

    def test_deploy_dashboard_to_cloudfront_update(self):
        cf = MagicMock()
        stack_outputs = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "BucketName", "OutputValue": "my-cf-bucket"},
                        {"OutputKey": "DistributionId", "OutputValue": "E12345EXAMPLE"},
                        {"OutputKey": "WebsiteURL", "OutputValue": "https://d123456789.cloudfront.net"},
                    ]
                }
            ]
        }
        cf.describe_stacks.return_value = stack_outputs
        waiter = MagicMock()
        cf.get_waiter.return_value = waiter

        s3 = MagicMock()
        session = MagicMock()
        session.client.side_effect = lambda svc, **kw: {"cloudformation": cf, "s3": s3}[svc]

        res = deploy_dashboard_to_cloudfront(
            session=session,
            region="eu-north-1",
            stack_name="aws-cost-alerts-cdn",
        )

        cf.update_stack.assert_called_once()
        waiter.wait.assert_called_once_with(StackName="aws-cost-alerts-cdn")
        s3.upload_file.assert_called_once()
        assert res["website_url"] == "https://d123456789.cloudfront.net"
