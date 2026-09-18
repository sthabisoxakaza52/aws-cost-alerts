import argparse
import math
import sys
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from .aws_clients import get_session, get_sts_client
from .sns import create_sns_topic
from .budget import create_budget
from .lambda_fn import create_slack_lambda
from .config import DEFAULT_BUDGET_NAME, DEFAULT_REGION, SUPPORTED_REGIONS


def parse_args():
    parser = argparse.ArgumentParser(
        prog="aws-cost-alerts",
        description=(
            "Provision AWS Budget alerts with "
            "email and optional Slack notifications."
        )
    )

    parser.add_argument(
        "--budget",
        required=True,
        type=float,
        help="Monthly AWS budget in USD"
    )

    parser.add_argument(
        "--email",
        required=True,
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

    return parser.parse_args()


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
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Slack webhook must be a valid HTTPS URL")


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


def main():
    args = parse_args()

    try:
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