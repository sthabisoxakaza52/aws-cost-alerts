import boto3


def get_session(profile=None, region=None):
    """
    Create a boto3 session.
    """
    return boto3.Session(profile_name=profile, region_name=region)


def get_sns_client(session):
    return session.client("sns")


def get_lambda_client(session):
    return session.client("lambda")

def get_iam_client(session):
    return session.client("iam")

def get_budgets_client(session):
    return session.client("budgets")


def get_sts_client(session):
    return session.client("sts")
