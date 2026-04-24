#!/usr/bin/env python3
"""
AWS Cost Alert Setup Script
Sets up AWS Budgets with SNS email + Slack webhook notifications
at 50%, 80%, 100%, and forecasted 100% thresholds.
"""

import boto3
import json
import argparse
import sys
from botocore.exceptions import ClientError


# ─── Configuration ────────────────────────────────────────────────────────────

DEFAULT_BUDGET_AMOUNT = "100"       # USD — override via --budget
DEFAULT_BUDGET_NAME   = "MonthlyAWSBudget"
DEFAULT_EMAIL         = ""          # override via --email
DEFAULT_SLACK_WEBHOOK = ""          # override via --slack-webhook
DEFAULT_REGION        = "us-east-1" # Budgets API only works in us-east-1

ALERT_THRESHOLDS = [
    {"percentage": 50,  "type": "PERCENTAGE",          "comparison": "GREATER_THAN"},
    {"percentage": 80,  "type": "PERCENTAGE",          "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "PERCENTAGE",          "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "FORECASTED_PERCENTAGE","comparison": "GREATER_THAN"},
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_account_id(session):
    sts = session.client("sts")
    return sts.get_caller_identity()["Account"]


def create_sns_topic(session, topic_name, email):
    """Create SNS topic and subscribe the email address."""
    sns = session.client("sns", region_name=DEFAULT_REGION)

    print(f"  Creating SNS topic '{topic_name}'...")
    resp = sns.create_topic(Name=topic_name)
    topic_arn = resp["TopicArn"]
    print(f"  Topic ARN: {topic_arn}")

    print(f"  Subscribing {email} to topic...")
    sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
    print(f"  Subscription pending — check {email} for confirmation email.")

    return topic_arn


def create_slack_lambda(session, slack_webhook_url, topic_arn):
    """
    Create a Lambda function that forwards SNS messages to Slack,
    then subscribe it to the SNS topic.
    """
    import zipfile, io, base64

    lambda_code = f'''
import urllib.request, json, os

SLACK_WEBHOOK = "{slack_webhook_url}"

def handler(event, context):
    for record in event.get("Records", []):
        message = record["Sns"]["Message"]
        subject = record["Sns"].get("Subject", "AWS Budget Alert")
        payload = json.dumps({{"text": f":warning: *{{subject}}*\\n{{message}}"}})
        req = urllib.request.Request(SLACK_WEBHOOK, data=payload.encode(), method="POST",
                                     headers={{"Content-Type": "application/json"}})
        urllib.request.urlopen(req)
    return {{"statusCode": 200}}
'''

    # Zip the code in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("lambda_function.py", lambda_code)
    buf.seek(0)
    zip_bytes = buf.read()

    iam = session.client("iam")
    lam = session.client("lambda", region_name=DEFAULT_REGION)
    sns = session.client("sns", region_name=DEFAULT_REGION)

    role_name   = "aws-cost-alert-lambda-role"
    lambda_name = "aws-cost-alert-slack-forwarder"

    # Create or reuse IAM role
    try:
        role = iam.get_role(RoleName=role_name)
        role_arn = role["Role"]["Arn"]
        print(f"  Reusing existing IAM role: {role_name}")
    except iam.exceptions.NoSuchEntityException:
        print(f"  Creating IAM role '{role_name}'...")
        trust = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Role for AWS Cost Alert Slack forwarder Lambda"
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        role_arn = role["Role"]["Arn"]
        print(f"  IAM role created: {role_arn}")
        import time; time.sleep(10)  # Let IAM propagate

    # Create or update Lambda
    try:
        fn = lam.get_function(FunctionName=lambda_name)
        print(f"  Updating existing Lambda '{lambda_name}'...")
        lam.update_function_code(FunctionName=lambda_name, ZipFile=zip_bytes)
        fn_arn = fn["Configuration"]["FunctionArn"]
    except lam.exceptions.ResourceNotFoundException:
        print(f"  Creating Lambda '{lambda_name}'...")
        fn = lam.create_function(
            FunctionName=lambda_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.handler",
            Code={"ZipFile": zip_bytes},
            Description="Forwards AWS Budget SNS alerts to Slack",
            Timeout=15,
        )
        fn_arn = fn["FunctionArn"]
    print(f"   Lambda ARN: {fn_arn}")

    # Allow SNS to invoke Lambda
    try:
        lam.add_permission(
            FunctionName=lambda_name,
            StatementId="sns-invoke",
            Action="lambda:InvokeFunction",
            Principal="sns.amazonaws.com",
            SourceArn=topic_arn,
        )
    except lam.exceptions.ResourceConflictException:
        pass  # Permission already exists

    # Subscribe Lambda to SNS topic
    print(f"  Subscribing Lambda to SNS topic...")
    sns.subscribe(TopicArn=topic_arn, Protocol="lambda", Endpoint=fn_arn)
    print(f"  Slack Lambda subscribed.")

    return fn_arn


def build_notifications(topic_arn):
    """Build the notifications + subscribers list for AWS Budgets."""
    notifications = []
    for t in ALERT_THRESHOLDS:
        threshold_type = "FORECASTED" if t["type"] == "FORECASTED_PERCENTAGE" else "ACTUAL"
        label = "forecasted" if threshold_type == "FORECASTED" else "actual"
        notifications.append({
            "Notification": {
                "NotificationType":          threshold_type,
                "ComparisonOperator":        t["comparison"],
                "Threshold":                 t["percentage"],
                "ThresholdType":             "PERCENTAGE",
                "NotificationState":         "ALARM",
            },
            "Subscribers": [
                {"SubscriptionType": "SNS", "Address": topic_arn}
            ]
        })
    return notifications


def create_budget(session, account_id, budget_name, budget_amount, topic_arn):
    """Create or overwrite the AWS Budget."""
    budgets = session.client("budgets", region_name=DEFAULT_REGION)

    budget = {
        "BudgetName":   budget_name,
        "BudgetType":   "COST",
        "TimeUnit":     "MONTHLY",
        "BudgetLimit":  {"Amount": str(budget_amount), "Unit": "USD"},
        "CostTypes": {
            "IncludeTax":              True,
            "IncludeSubscription":     True,
            "UseBlended":              False,
            "IncludeRefund":           False,
            "IncludeCredit":           False,
            "IncludeUpfront":          True,
            "IncludeRecurring":        True,
            "IncludeOtherSubscription":True,
            "IncludeSupport":          True,
            "IncludeDiscount":         True,
            "UseAmortized":            False,
        }
    }

    notifications = build_notifications(topic_arn)

    # Delete existing budget if present (can't update+notifications in one call)
    try:
        budgets.delete_budget(AccountId=account_id, BudgetName=budget_name)
        print(f"   Deleted existing budget '{budget_name}' to recreate it.")
    except budgets.exceptions.NotFoundException:
        pass

    print(f"   Creating budget '{budget_name}' (${budget_amount}/month)...")
    budgets.create_budget(
        AccountId=account_id,
        Budget=budget,
        NotificationsWithSubscribers=notifications,
    )
    print(f"   Budget created with {len(notifications)} alert thresholds.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Set up AWS monthly cost alerts (email + Slack)."
    )
    p.add_argument("--budget",        required=True,
                   help="Monthly budget limit in USD (e.g. 200)")
    p.add_argument("--email",         required=True,
                   help="Email address for SNS alert subscription")
    p.add_argument("--slack-webhook", required=True,
                   help="Slack incoming webhook URL")
    p.add_argument("--budget-name",   default=DEFAULT_BUDGET_NAME,
                   help=f"Name for the AWS Budget (default: {DEFAULT_BUDGET_NAME})")
    p.add_argument("--profile",       default=None,
                   help="AWS CLI profile to use (default: default)")
    p.add_argument("--dry-run",       action="store_true",
                   help="Print what would be created without making changes")
    return p.parse_args()


def main():
    args = parse_args()

    if args.dry_run:
        print("\n[DRY RUN] The following resources would be created:")
        print(f"  • SNS Topic:    aws-cost-alert-topic  (region: {DEFAULT_REGION})")
        print(f"  • Email sub:    {args.email}")
        print(f"  • Slack Lambda: aws-cost-alert-slack-forwarder")
        print(f"  • IAM Role:     aws-cost-alert-lambda-role")
        print(f"  • Budget:       {args.budget_name}  (${args.budget}/month)")
        print(f"  • Alerts at:    50% | 80% | 100% actual + 100% forecasted")
        print()
        sys.exit(0)

    session = boto3.Session(profile_name=args.profile)

    print("\n─── AWS Cost Alert Setup ───────────────────────────────")

    print("\n[1/4] Resolving AWS account ID...")
    account_id = get_account_id(session)
    print(f"   Account ID: {account_id}")

    print("\n[2/4] Setting up SNS topic + email subscription...")
    topic_arn = create_sns_topic(session, "aws-cost-alert-topic", args.email)

    print("\n[3/4] Deploying Slack forwarder Lambda...")
    create_slack_lambda(session, args.slack_webhook, topic_arn)

    print("\n[4/4] Creating AWS Budget with alert thresholds...")
    create_budget(session, account_id, args.budget_name, args.budget, topic_arn)

    print("\nDone! Summary:")
    print(f"   Budget:    ${args.budget}/month  ({args.budget_name})")
    print(f"   Alerts:    50% · 80% · 100% actual · 100% forecasted")
    print(f"   Email:     {args.email}  ← confirm the SNS subscription email!")
    print(f"   Slack:     via Lambda forwarder")
    print()


if __name__ == "__main__":
    main()