from botocore.exceptions import ClientError
from .config import DEFAULT_REGION


def create_sns_topic(session, topic_name, email):
    sns = session.client("sns", region_name=DEFAULT_REGION)

    try:
        print(f"Creating SNS topic '{topic_name}'...")
        resp = sns.create_topic(Name=topic_name)
        topic_arn = resp["TopicArn"]

        print(f"Subscribing {email}...")
        sns.subscribe(
            TopicArn=topic_arn,
            Protocol="email",
            Endpoint=email
        )

        return topic_arn

    except ClientError as e:
        print(f"Error creating SNS topic: {e}")
        raise