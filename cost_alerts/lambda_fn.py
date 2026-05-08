import json
import zipfile
import io
import time

from .aws_client import (
    get_lambda_client,
    get_iam_client,
    get_sns_client
)

from .config import DEFAULT_REGION


def build_lambda_code(slack_webhook_url):
    return f'''
import urllib.request
import json

SLACK_WEBHOOK = "{slack_webhook_url}"

def handler(event, context):
    for record in event.get("Records", []):
        message = record["Sns"]["Message"]
        subject = record["Sns"].get("Subject", "AWS Budget Alert")

        payload = json.dumps({{
            "text": f":warning: *{{subject}}*\\n{{message}}"
        }})

        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=payload.encode(),
            headers={{"Content-Type": "application/json"}}
        )

        urllib.request.urlopen(req)

    return {{"statusCode": 200}}
'''


def create_slack_lambda(session, slack_webhook_url, topic_arn):

    lambda_code = build_lambda_code(slack_webhook_url)

    # Create ZIP package
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("lambda_function.py", lambda_code)

    buffer.seek(0)

    lambda_client = get_lambda_client(session)
    iam_client = get_iam_client(session)
    sns_client = get_sns_client(session)

    role_name = "aws-cost-alert-lambda-role"
    lambda_name = "aws-cost-alert-slack-forwarder"

    # Create or reuse IAM role
    try:
        role = iam_client.get_role(RoleName=role_name)
        role_arn = role["Role"]["Arn"]

        print(f"Using existing IAM role: {role_name}")

    except iam_client.exceptions.NoSuchEntityException:

        print(f"Creating IAM role: {role_name}")

        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }]
        }

        role = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Lambda role for AWS cost alerts"
        )

        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=(
                "arn:aws:iam::aws:policy/"
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        role_arn = role["Role"]["Arn"]

        # wait for IAM propagation
        time.sleep(10)

    # Create or update Lambda
    try:
        existing = lambda_client.get_function(
            FunctionName=lambda_name
        )

        print(f"Updating existing Lambda: {lambda_name}")

        lambda_client.update_function_code(
            FunctionName=lambda_name,
            ZipFile=buffer.read()
        )

        lambda_arn = existing["Configuration"]["FunctionArn"]

    except lambda_client.exceptions.ResourceNotFoundException:

        print(f"Creating Lambda: {lambda_name}")

        response = lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.handler",
            Code={"ZipFile": buffer.read()},
            Timeout=15,
            Description="SNS to Slack AWS budget alerts"
        )

        lambda_arn = response["FunctionArn"]

    print(f"Lambda ARN: {lambda_arn}")

    # Allow SNS to invoke Lambda
    try:
        lambda_client.add_permission(
            FunctionName=lambda_name,
            StatementId="sns-invoke",
            Action="lambda:InvokeFunction",
            Principal="sns.amazonaws.com",
            SourceArn=topic_arn
        )

    except lambda_client.exceptions.ResourceConflictException:
        pass

    # Subscribe Lambda to SNS
    sns_client.subscribe(
        TopicArn=topic_arn,
        Protocol="lambda",
        Endpoint=lambda_arn
    )

    print("Slack Lambda subscribed to SNS.")

    return lambda_arn