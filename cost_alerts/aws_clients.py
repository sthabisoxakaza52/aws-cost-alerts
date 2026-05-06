import boto3 
from .config import DEFAULT_REGION

def get_session(profile=None):
    """
    Create a boto3 session.
    """
    return boto3.Session(profile_name=profile)

def get_sns_client(session):
    return session.client("sns" , region_name=DEFAULT_REGION)

def get_lambda_client(session):
    return session.client("lambda" , region_name=DEFAULT_REGION)

def get_iam_client(session):
    return session.client("iam")

def get_budgets_client(session):
    return session.client("budgets" , region_name=DEFAULT_REGION)

def get_sts_client(session):
    return session.client("sts")
