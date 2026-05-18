#!/usr/bin/env python3
"""
AWS Cost Alert Setup
Sets up AWS Budgets with SNS email + Slack webhook notifications
at 50%, 80%, 100%, and forecasted-100% thresholds.

Compatible with Windows (PowerShell / CMD), macOS, and Linux.
"""

import boto3
import json
import argparse
import sys
import time
import threading
import itertools
import platform
from botocore.exceptions import ClientError


IS_WINDOWS = platform.system() == "Windows"

# Enable ANSI escape codes on Windows 10+
if IS_WINDOWS:
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    WHITE  = "\033[97m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    GREY   = "\033[90m"


def c(color, text):
    return f"{color}{text}{C.RESET}"


class Spinner:
    """Context-manager spinner. Shows a success/failure tick on exit."""

    FRAMES     = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    FRAMES_WIN = ["|", "/", "-", "\\"]  # braille may not render on older Windows terminals

    def __init__(self, label: str, indent: int = 4):
        self.label   = label
        self.indent  = indent
        self._stop   = threading.Event()
        self._thread = None
        self.frames  = self.FRAMES_WIN if IS_WINDOWS else self.FRAMES

    def _spin(self):
        pad = " " * self.indent
        for frame in itertools.cycle(self.frames):
            if self._stop.is_set():
                break
            sys.stdout.write(f"\r{pad}{c(C.CYAN, frame)}  {self.label} ")
            sys.stdout.flush()
            time.sleep(0.08)

    def __enter__(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        self._thread.join()
        pad  = " " * self.indent
        icon = c(C.GREEN, "✔") if exc_type is None else c(C.RED, "✘")
        sys.stdout.write(f"\r{pad}{icon}  {self.label}{' ' * 10}\n")
        sys.stdout.flush()
        return False


BORDER = "═" * 58


def header():
    print()
    print(c(C.CYAN, f"  ╔{BORDER}╗"))
    print(c(C.CYAN, "  ║") + c(C.BOLD + C.WHITE, "  AWS Cost Alert Setup".center(58)) + c(C.CYAN, "║"))
    print(c(C.CYAN, f"  ╚{BORDER}╝"))
    print()


def section(step: int, total: int, title: str):
    print(f"\n  {c(C.GREY, f'[{step}/{total}]')}  {c(C.BOLD + C.WHITE, title)}")
    print(c(C.GREY, "  " + "─" * 54))


def info(key: str, value: str, indent: int = 6):
    print(f"{' ' * indent}{c(C.GREY, key.ljust(18))} {c(C.CYAN, value)}")


def note(text: str, indent: int = 6):
    print(f"{' ' * indent}{c(C.YELLOW, '⚠')}  {c(C.DIM, text)}")


def success_banner(budget, budget_name, email, has_slack):
    w = 58
    print()
    print(c(C.GREEN, f"  ╔{'═' * w}╗"))
    print(c(C.GREEN, "  ║") + c(C.BOLD + C.WHITE, "  Setup Complete".center(w)) + c(C.GREEN, "║"))
    print(c(C.GREEN, f"  ╠{'═' * w}╣"))

    def row(label, value):
        pad = w - (2 + 20 + len(value))
        print(c(C.GREEN, "  ║") + c(C.WHITE, f"  {label:<20}") + c(C.CYAN, value) + " " * max(pad, 1) + c(C.GREEN, "║"))

    row("Budget:",    f"${budget}/month  ({budget_name})")
    row("Alerts at:", "50%  ·  80%  ·  100% actual  ·  100% forecast")
    row("Email:",     email)
    if has_slack:
        row("Slack:", "via Lambda forwarder  ✔")

    print(c(C.GREEN, f"  ╠{'═' * w}╣"))
    print(c(C.GREEN, "  ║") + c(C.YELLOW, "  ➜  Confirm the SNS subscription in your inbox!").ljust(w + 9) + c(C.GREEN, "║"))
    print(c(C.GREEN, f"  ╚{'═' * w}╝"))
    print()


def dry_run_banner(args):
    w = 58
    print()
    print(c(C.YELLOW, f"  ╔{'═' * w}╗"))
    print(c(C.YELLOW, "  ║") + c(C.BOLD + C.WHITE, "  DRY RUN — No changes will be made".center(w)) + c(C.YELLOW, "║"))
    print(c(C.YELLOW, f"  ╠{'═' * w}╣"))

    rows = [
        ("SNS Topic",    "aws-cost-alert-topic"),
        ("Email sub",    args.email),
        ("Slack Lambda", "aws-cost-alert-slack-forwarder" if args.slack_webhook else "skipped"),
        ("IAM Role",     "aws-cost-alert-lambda-role"     if args.slack_webhook else "skipped"),
        ("Budget",       f"{args.budget_name}  (${args.budget}/month)"),
        ("Alert levels", "50%  |  80%  |  100% actual  |  100% forecasted"),
    ]
    for label, value in rows:
        pad = w - (2 + 20 + len(value))
        print(c(C.YELLOW, "  ║") + c(C.WHITE, f"  {label:<20}") + c(C.CYAN, value) + " " * max(pad, 1) + c(C.YELLOW, "║"))

    print(c(C.YELLOW, f"  ╚{'═' * w}╝"))
    print()


DEFAULT_BUDGET_NAME = "MonthlyAWSBudget"
DEFAULT_REGION      = "us-east-1"

ALERT_THRESHOLDS = [
    {"percentage": 50,  "type": "PERCENTAGE",            "comparison": "GREATER_THAN"},
    {"percentage": 80,  "type": "PERCENTAGE",            "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "PERCENTAGE",            "comparison": "GREATER_THAN"},
    {"percentage": 100, "type": "FORECASTED_PERCENTAGE", "comparison": "GREATER_THAN"},
]


def get_account_id(session):
    return session.client("sts").get_caller_identity()["Account"]


def create_sns_topic(session, topic_name, email):
    sns = session.client("sns", region_name=DEFAULT_REGION)

    with Spinner(f"Creating SNS topic '{topic_name}'"):
        topic_arn = sns.create_topic(Name=topic_name)["TopicArn"]
    info("Topic ARN", topic_arn)

    with Spinner(f"Subscribing {email}"):
        sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
    note(f"Subscription pending — check {email} for a confirmation email.")

    return topic_arn


def create_slack_lambda(session, slack_webhook_url, topic_arn):
    import zipfile, io

    lambda_code = f'''
import urllib.request, json

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

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("lambda_function.py", lambda_code)
    buf.seek(0)
    zip_bytes = buf.read()

    iam = session.client("iam")
    lam = session.client("lambda", region_name=DEFAULT_REGION)
    sns = session.client("sns",    region_name=DEFAULT_REGION)

    role_name   = "aws-cost-alert-lambda-role"
    lambda_name = "aws-cost-alert-slack-forwarder"

    try:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        with Spinner(f"Reusing IAM role '{role_name}'"):
            time.sleep(0.4)
    except iam.exceptions.NoSuchEntityException:
        with Spinner(f"Creating IAM role '{role_name}'"):
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
                Description="Execution role for the cost-alert Slack forwarder",
            )
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            )
            role_arn = role["Role"]["Arn"]
            time.sleep(10)  # wait for IAM to propagate before Lambda creation

    info("IAM Role ARN", role_arn)

    try:
        fn     = lam.get_function(FunctionName=lambda_name)
        fn_arn = fn["Configuration"]["FunctionArn"]
        with Spinner(f"Updating Lambda '{lambda_name}'"):
            lam.update_function_code(FunctionName=lambda_name, ZipFile=zip_bytes)
    except lam.exceptions.ResourceNotFoundException:
        with Spinner(f"Creating Lambda '{lambda_name}'"):
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

    info("Lambda ARN", fn_arn)

    with Spinner("Granting SNS invoke permission"):
        try:
            lam.add_permission(
                FunctionName=lambda_name,
                StatementId="sns-invoke",
                Action="lambda:InvokeFunction",
                Principal="sns.amazonaws.com",
                SourceArn=topic_arn,
            )
        except lam.exceptions.ResourceConflictException:
            pass  # permission already exists

    with Spinner("Subscribing Lambda to SNS topic"):
        sns.subscribe(TopicArn=topic_arn, Protocol="lambda", Endpoint=fn_arn)

    return fn_arn


def build_notifications(topic_arn):
    notifications = []
    for t in ALERT_THRESHOLDS:
        threshold_type = "FORECASTED" if t["type"] == "FORECASTED_PERCENTAGE" else "ACTUAL"
        notifications.append({
            "Notification": {
                "NotificationType":   threshold_type,
                "ComparisonOperator": t["comparison"],
                "Threshold":          t["percentage"],
                "ThresholdType":      "PERCENTAGE",
                "NotificationState":  "ALARM",
            },
            "Subscribers": [{"SubscriptionType": "SNS", "Address": topic_arn}],
        })
    return notifications


def create_budget(session, account_id, budget_name, budget_amount, topic_arn):
    budgets       = session.client("budgets", region_name=DEFAULT_REGION)
    notifications = build_notifications(topic_arn)

    budget = {
        "BudgetName":  budget_name,
        "BudgetType":  "COST",
        "TimeUnit":    "MONTHLY",
        "BudgetLimit": {"Amount": str(budget_amount), "Unit": "USD"},
        "CostTypes": {
            "IncludeTax":               True,
            "IncludeSubscription":      True,
            "UseBlended":               False,
            "IncludeRefund":            False,
            "IncludeCredit":            False,
            "IncludeUpfront":           True,
            "IncludeRecurring":         True,
            "IncludeOtherSubscription": True,
            "IncludeSupport":           True,
            "IncludeDiscount":          True,
            "UseAmortized":             False,
        },
    }

    with Spinner(f"Checking for existing budget '{budget_name}'"):
        try:
            budgets.delete_budget(AccountId=account_id, BudgetName=budget_name)
        except budgets.exceptions.NotFoundException:
            pass  # nothing to delete

    with Spinner(f"Creating budget '{budget_name}' (${budget_amount}/month)"):
        budgets.create_budget(
            AccountId=account_id,
            Budget=budget,
            NotificationsWithSubscribers=notifications,
        )

    info("Thresholds", f"{len(notifications)} alert levels configured")


def parse_args():
    p = argparse.ArgumentParser(
        description="Set up AWS monthly cost alerts (email + optional Slack).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples
--------
  Windows PowerShell:
    python setup_cost_alerts.py `
      --budget 150 `
      --email alerts@mycompany.com `
      --slack-webhook https://hooks.slack.com/services/T00/B00/xxx

  Windows CMD:
    python setup_cost_alerts.py ^
      --budget 150 ^
      --email alerts@mycompany.com ^
      --slack-webhook https://hooks.slack.com/services/T00/B00/xxx

  macOS / Linux / Git Bash:
    python3 setup_cost_alerts.py \\
      --budget 150 \\
      --email alerts@mycompany.com \\
      --slack-webhook https://hooks.slack.com/services/T00/B00/xxx

  Dry run (preview only):
    python setup_cost_alerts.py --budget 150 --email you@example.com --dry-run
"""
    )
    p.add_argument("--budget",        required=True,  help="Monthly budget limit in USD (e.g. 200)")
    p.add_argument("--email",         required=True,  help="Email address for SNS alert subscription")
    p.add_argument("--slack-webhook", default=None,   help="Slack incoming webhook URL (optional)")
    p.add_argument("--budget-name",   default=DEFAULT_BUDGET_NAME,
                   help=f"Name for the AWS Budget (default: {DEFAULT_BUDGET_NAME})")
    p.add_argument("--profile",       default=None,   help="AWS CLI profile to use (default: default)")
    p.add_argument("--dry-run",       action="store_true",
                   help="Preview resources that would be created, without making changes")
    return p.parse_args()


def main():
    args    = parse_args()
    session = boto3.Session(profile_name=args.profile)
    header()

    if args.dry_run:
        dry_run_banner(args)
        sys.exit(0)

    total_steps = 4 if args.slack_webhook else 3

    section(1, total_steps, "Resolving AWS account identity")
    with Spinner("Fetching account ID"):
        account_id = get_account_id(session)
    info("Account ID", account_id)

    section(2, total_steps, "Setting up SNS topic & email subscription")
    topic_arn = create_sns_topic(session, "aws-cost-alert-topic", args.email)

    if args.slack_webhook:
        section(3, total_steps, "Deploying Slack forwarder Lambda")
        create_slack_lambda(session, args.slack_webhook, topic_arn)

    section(total_steps, total_steps, "Creating AWS Budget with alert thresholds")
    create_budget(session, account_id, args.budget_name, args.budget, topic_arn)

    success_banner(args.budget, args.budget_name, args.email, bool(args.slack_webhook))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {c(C.YELLOW, '⚠')}  Setup interrupted.\n")
        sys.exit(1)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg  = e.response["Error"]["Message"]
        print(f"\n  {c(C.RED, '✘')}  AWS Error [{c(C.YELLOW, code)}]: {msg}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n  {c(C.RED, '✘')}  Unexpected error: {e}\n")
        sys.exit(1)