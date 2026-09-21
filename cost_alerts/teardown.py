"""Automated teardown / cleanup for provisioned AWS cost alert resources."""

from botocore.exceptions import ClientError

from .aws_clients import get_iam_client, get_lambda_client, get_sns_client
from .config import DEFAULT_BUDGET_NAME, DEFAULT_REGION


def teardown_resources(
    session,
    account_id,
    budget_name=DEFAULT_BUDGET_NAME,
    topic_name="aws-cost-alert-topic",
    lambda_name="aws-cost-alert-slack-forwarder",
    role_name="aws-cost-alert-lambda-role",
    region=DEFAULT_REGION,
):
    """
    Tear down AWS resources provisioned by aws-cost-alerts.
    Deletes:
      1. AWS Budget
      2. SNS Topic
      3. Lambda Function (Slack forwarder)
      4. IAM Role (Lambda execution role)
    Idempotent: skips resources that do not exist.
    """
    results = {}

    # 1. AWS Budget
    budgets = session.client("budgets")
    print(f"[1/4] Deleting AWS Budget '{budget_name}'...")
    try:
        budgets.delete_budget(AccountId=account_id, BudgetName=budget_name)
        print(f"  Deleted budget: {budget_name}")
        results["budget"] = "deleted"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NotFoundException", "ResourceNotFoundException"):
            print(f"  Budget '{budget_name}' not found, skipping.")
            results["budget"] = "not_found"
        else:
            raise

    # 2. SNS Topic
    sns = get_sns_client(session)
    topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
    print(f"[2/4] Deleting SNS Topic '{topic_name}'...")
    try:
        sns.delete_topic(TopicArn=topic_arn)
        print(f"  Deleted SNS topic: {topic_name}")
        results["sns"] = "deleted"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NotFoundException", "ResourceNotFoundException"):
            print(f"  SNS topic '{topic_name}' not found, skipping.")
            results["sns"] = "not_found"
        else:
            raise

    # 3. Lambda Function
    lambda_client = get_lambda_client(session)
    print(f"[3/4] Deleting Lambda Function '{lambda_name}'...")
    try:
        lambda_client.delete_function(FunctionName=lambda_name)
        print(f"  Deleted Lambda function: {lambda_name}")
        results["lambda"] = "deleted"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("ResourceNotFoundException", "NotFoundException"):
            print(f"  Lambda function '{lambda_name}' not found, skipping.")
            results["lambda"] = "not_found"
        else:
            raise

    # 4. IAM Role
    iam = get_iam_client(session)
    print(f"[4/4] Deleting IAM Role '{role_name}'...")
    policy_arn = (
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    )
    try:
        iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in ("NoSuchEntity", "NoSuchEntityException"):
            raise

    try:
        iam.delete_role(RoleName=role_name)
        print(f"  Deleted IAM role: {role_name}")
        results["iam_role"] = "deleted"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NoSuchEntity", "NoSuchEntityException"):
            print(f"  IAM role '{role_name}' not found, skipping.")
            results["iam_role"] = "not_found"
        else:
            raise

    return results
