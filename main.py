#!/usr/bin/env python3

import boto3
import argparse

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--budget", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--slack-webhook", required=True)
    p.add_argument("--budget-name", default="MonthlyBudget")
    p.add_argument("--profile", default=None)
    return p.parse_args()

def get_account_id(session):
    sts = session.client("sts")
    return sts.get_caller_identity()["Account"]

def main():
    args = parse_args()
    session = boto3.Session(profile_name=args.profile)
    account_id = get_account_id(session)
    print(account_id)

if __name__ == "__main__":
    main()