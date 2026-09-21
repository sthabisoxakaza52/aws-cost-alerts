import argparse
import math
import sys
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from .aws_clients import get_session, get_sts_client
from .sns import create_sns_topic
from .budget import create_budget
from .lambda_fn import create_slack_lambda
from .teardown import teardown_resources
from .dashboard import get_dashboard_path, launch_dashboard, deploy_dashboard_to_s3
from .config import DEFAULT_BUDGET_NAME, DEFAULT_REGION, SUPPORTED_REGIONS


def build_parser():
    parser = argparse.ArgumentParser(
        prog="aws-cost-alerts",
        description=(
            "Provision AWS Budget alerts with "
            "email and optional Slack notifications."
        )
    )

    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Monthly AWS budget in USD"
    )

    parser.add_argument(
        "--email",
        default=None,
        help="Email address for AWS budget alerts"
    )

    parser.add_argument(
        "--slack-webhook",
        default=None,
        help="Slack incoming webhook URL (optional)"
    )

    parser.add_argument(
        "--budget-name",
        default=DEFAULT_BUDGET_NAME,
        help="Custom AWS Budget name"
    )

    parser.add_argument(
        "--profile",
        default=None,
        help="AWS CLI profile to use"
    )

    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region to use (default: {DEFAULT_REGION})"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview resources without creating them"
    )

    parser.add_argument(
        "--destroy",
        action="store_true",
        help="Tear down provisioned AWS cost alert resources"
    )

    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Launch or preview the interactive AWS Cost Alerts dashboard"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for dashboard local server (default: 8000)"
    )

    parser.add_argument(
        "--deploy-dashboard",
        action="store_true",
        help="Deploy the interactive dashboard to an Amazon S3 static website bucket"
    )

    return parser


def parse_args(args=None):
    return build_parser().parse_args(args)


def get_account_id(session):
    sts = get_sts_client(session)
    return sts.get_caller_identity()["Account"]


def validate_budget(amount):
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Budget must be greater than 0")


def validate_region(region):
    if region not in SUPPORTED_REGIONS:
        supported = ", ".join(SUPPORTED_REGIONS)
        raise ValueError(f"Unsupported region '{region}'. Use one of: {supported}")


def validate_email(email):
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Email must be a valid email address")


def validate_budget_name(name):
    if not name.strip():
        raise ValueError("Budget name cannot be empty")


def validate_slack_webhook(webhook):
    if webhook is None:
        return

    parsed = urlparse(webhook)
    host = parsed.netloc.lower()
    allowed_hosts = (
        "hooks.slack.com",
        "hooks.slack.com.cn",
        "hooks.slack-edge.com",
    )

    if parsed.scheme != "https" or not host or host not in allowed_hosts:
        raise ValueError(
            "Slack webhook must be a valid HTTPS URL for a Slack webhook host"
        )


def print_dry_run(args):
    print("\nAWS Cost Alerts Setup")
    print("=" * 40)

    print("\nDry Run Mode")
    print("-" * 40)
    print("No AWS resources will be modified.")

    print(f"Budget Amount : ${args.budget}")
    print(f"Budget Name   : {args.budget_name}")
    print(f"Alert Email   : {args.email}")
    print(f"AWS Profile   : {args.profile or 'default'}")
    print(f"AWS Region    : {args.region}")

    print("\nResources to be created:")
    print(" - SNS Topic")
    print(" - Email Subscription")
    if args.slack_webhook:
        print(" - Slack Lambda")
        print(" - IAM Role")
    print(" - AWS Budget")

    print("\nAlert Thresholds:")
    print(" - 50% Actual")
    print(" - 80% Actual")
    print(" - 100% Actual")
    print(" - 100% Forecasted")


def print_destroy_dry_run(args):
    print("\nAWS Cost Alerts Teardown")
    print("=" * 40)

    print("\nDry Run Mode")
    print("-" * 40)
    print("No AWS resources will be modified.")

    print(f"Budget Name   : {args.budget_name}")
    print(f"AWS Profile   : {args.profile or 'default'}")
    print(f"AWS Region    : {args.region}")

    print("\nResources to be deleted:")
    print(f" - AWS Budget: {args.budget_name}")
    print(" - SNS Topic: aws-cost-alert-topic")
    print(" - Lambda Function: aws-cost-alert-slack-forwarder")
    print(" - IAM Role: aws-cost-alert-lambda-role")


def print_dashboard_dry_run(args):
    path = get_dashboard_path()
    print("\nAWS Cost Alerts Dashboard")
    print("=" * 40)

    print("\nDry Run Mode")
    print("-" * 40)
    print(f"Dashboard File : {path}")
    print(f"File Exists    : {path.exists()}")
    print(f"Target URL     : {path.as_uri()}")
    print(f"Server Port    : {args.port}")
    print("Browser launch suppressed in dry-run mode.")


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.dashboard:
            if args.dry_run:
                print_dashboard_dry_run(args)
                sys.exit(0)

            print("\nAWS Cost Alerts Dashboard")
            print("=" * 40)
            launch_dashboard(port=args.port, open_browser=True)
            sys.exit(0)

        if args.deploy_dashboard:
            validate_region(args.region)

            if args.dry_run:
                print("\nAWS Cost Alerts Dashboard S3 Deployment")
                print("=" * 40)
                print("\nDry Run Mode")
                print("-" * 40)
                print(f"Target Region : {args.region}")
                print(f"Dashboard File: {get_dashboard_path()}")
                print("Bucket creation and S3 upload suppressed in dry-run mode.")
                sys.exit(0)

            print("\nAWS Cost Alerts Dashboard S3 Deployment")
            print("=" * 40)
            session = get_session(args.profile, args.region)
            print("\nConnecting to AWS...")
            account_id = get_account_id(session)
            print(f"Connected to AWS Account: {account_id}\n")

            deploy_dashboard_to_s3(
                session=session,
                account_id=account_id,
                region=args.region
            )
            sys.exit(0)

        if args.destroy:
            validate_region(args.region)
            validate_budget_name(args.budget_name)

            if args.dry_run:
                print_destroy_dry_run(args)
                sys.exit(0)

            print("\nAWS Cost Alerts Teardown")
            print("=" * 40)

            session = get_session(args.profile, args.region)

            print("\nConnecting to AWS...")
            account_id = get_account_id(session)
            print(f"Connected to AWS Account: {account_id}\n")

            teardown_resources(
                session=session,
                account_id=account_id,
                budget_name=args.budget_name,
                region=args.region,
            )

            print("\nAWS cost alert resources successfully cleaned up.")
            sys.exit(0)

        # Normal setup workflow requires --budget and --email
        if args.budget is None or args.email is None:
            missing = []
            if args.budget is None:
                missing.append("--budget")
            if args.email is None:
                missing.append("--email")
            parser.error(f"the following arguments are required: {', '.join(missing)}")

        validate_budget(args.budget)
        validate_region(args.region)
        validate_email(args.email)
        validate_budget_name(args.budget_name)
        validate_slack_webhook(args.slack_webhook)

        if args.dry_run:
            print_dry_run(args)
            sys.exit(0)

        print("\nAWS Cost Alerts Setup")
        print("=" * 40)

        session = get_session(args.profile, args.region)

        print("\n[1/4] Connecting to AWS...")
        account_id = get_account_id(session)

        print(f"Connected to AWS Account: {account_id}")

        print("\n[2/4] Creating SNS topic...")
        topic_arn = create_sns_topic(
            session=session,
            topic_name="aws-cost-alert-topic",
            email=args.email
        )

        total_steps = 4 if args.slack_webhook else 3

        if args.slack_webhook:
            print(f"\n[3/{total_steps}] Deploying Slack Lambda...")
            create_slack_lambda(
                session=session,
                slack_webhook_url=args.slack_webhook,
                topic_arn=topic_arn
            )

        print(f"\n[{total_steps}/{total_steps}] Creating AWS Budget...")
        create_budget(
            session=session,
            account_id=account_id,
            budget_name=args.budget_name,
            budget_amount=args.budget,
            topic_arn=topic_arn
        )

        print("\nAWS cost alerts successfully configured.")

        print("\nNext Steps:")
        print("1. Confirm the SNS email subscription.")
        print("2. Test the SNS topic.")
        if args.slack_webhook:
            print("3. Verify Slack notifications.")

    except ValueError as error:
        print(f"\nValidation Error: {error}")
        sys.exit(1)

    except ClientError as error:
        print(f"\nAWS Error: {error}")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(1)

    except Exception as error:
        print(f"\nUnexpected Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()