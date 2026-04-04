#!/usr/bin/env python3
"""
One-time setup: creates an AWS IAM OIDC provider + role so GitHub Actions
can call AWS Bedrock without storing long-lived credentials as secrets.

Run ONCE locally with your SSO profile:
    AWS_PROFILE=aws-sandbox-personal-36 python setup_aws_oidc.py

Then add the printed role ARN as a GitHub secret: AWS_ROLE_ARN
"""
import json
import boto3

ACCOUNT_ID  = "599843985030"
REGION      = "eu-west-1"
REPO        = "kobyal/ai-news-briefing"   # GitHub repo that will assume this role
ROLE_NAME   = "GitHubActionsBedrockRole"
OIDC_URL    = "https://token.actions.githubusercontent.com"
OIDC_THUMB  = "6938fd4d98bab03faadb97b34396831e3780aea1"  # GitHub OIDC thumbprint

iam = boto3.client("iam")


# 1. Create OIDC provider (idempotent — skip if already exists)
try:
    iam.create_open_id_connect_provider(
        Url=OIDC_URL,
        ClientIDList=["sts.amazonaws.com"],
        ThumbprintList=[OIDC_THUMB],
    )
    print(f"✓ Created OIDC provider: {OIDC_URL}")
except iam.exceptions.EntityAlreadyExistsException:
    print(f"  OIDC provider already exists: {OIDC_URL}")


# 2. Trust policy — only this repo can assume the role
trust_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "Federated": f"arn:aws:iam::{ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {
            "StringEquals": {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
            },
            "StringLike": {
                "token.actions.githubusercontent.com:sub": f"repo:{REPO}:*"
            }
        }
    }]
}

# 3. Bedrock permission policy
bedrock_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": [
            "bedrock:InvokeModel",
            "bedrock:InvokeModelWithResponseStream",
        ],
        "Resource": "*"
    }]
}

# 4. Create role (idempotent)
try:
    role = iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="GitHub Actions role for AI news briefing - Bedrock access only",
        MaxSessionDuration=3600,
    )
    role_arn = role["Role"]["Arn"]
    print(f"✓ Created role: {role_arn}")
except iam.exceptions.EntityAlreadyExistsException:
    role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{ROLE_NAME}"
    print(f"  Role already exists: {role_arn}")

# 5. Attach inline Bedrock policy
iam.put_role_policy(
    RoleName=ROLE_NAME,
    PolicyName="BedrockInvoke",
    PolicyDocument=json.dumps(bedrock_policy),
)
print(f"✓ Attached BedrockInvoke policy")

print()
print("=" * 60)
print("  Setup complete. Add this as a GitHub Actions secret:")
print()
print(f"  Secret name : AWS_ROLE_ARN")
print(f"  Secret value: {role_arn}")
print("=" * 60)
