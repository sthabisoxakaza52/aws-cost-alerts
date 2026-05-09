import argparse
import sys

from botocore.exceptions import ClientError

from .aws_client import get_session, get_sts_client
from .sns import create_sns_topic
from .budget import create_budget
from .lambda_fn import create_slack_lambda
from .config import DEFAULT_BUDGET_NAME


def parse_args():
    parser = argparse.ArgumentParser(
        prog="aws-cost-alerts",
        description=(
            "Provision AWS Budget alerts with "
            "Email and Slack notifications."
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
        required=True,
        help="Slack incoming webhook URL"
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
        "--dry-run",
        action="store_true",
        help="Preview resources without creating them"
    )

    return parser.parse_args()


def get_account_id(session):
    sts = get_sts_client(session)
    return sts.get_caller_identity()["Account"]


def validate_budget(amount):
    if amount <= 0:
        raise ValueError("Budget must be greater than 0")


def print_dry_run(args):
    print("\nAWS Cost Alerts Setup")
    print("=" * 40)

    print("\nDry Run Mode")
    print("-" * 40)

    print(f"Budget Amount : ${args.budget}")
    print(f"Budget Name   : {args.budget_name}")
    print(f"Alert Email   : {args.email}")
    print(f"AWS Profile   : {args.profile or 'default'}")

    print("\nResources to be created:")
    print(" - SNS Topic")
    print(" - Email Subscription")
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

        if args.dry_run:
            print_dry_run(args)
            sys.exit(0)

        print("\nAWS Cost Alerts Setup")
        print("=" * 40)

        session = get_session(args.profile)

        print("\n[1/4] Connecting to AWS...")
        account_id = get_account_id(session)

        print(f"Connected to AWS Account: {account_id}")

        print("\n[2/4] Creating SNS topic...")
        topic_arn = create_sns_topic(
            session=session,
            topic_name="aws-cost-alert-topic",
            email=args.email
        )

        print("\n[3/4] Deploying Slack Lambda...")
        create_slack_lambda(
            session=session,
            slack_webhook_url=args.slack_webhook,
            topic_arn=topic_arn
        )

        print("\n[4/4] Creating AWS Budget...")
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