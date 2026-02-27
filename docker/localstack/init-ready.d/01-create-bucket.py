#!/usr/bin/env python3
"""Create the default S3 bucket when LocalStack is ready."""

import os

import boto3

bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME", "eu-fact-force")
region = os.environ.get("AWS_S3_REGION_NAME", "eu-west-1")

client = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    region_name=region,
)
try:
    client.create_bucket(Bucket=bucket)
    print(f"Created bucket: {bucket}")
except client.exceptions.BucketAlreadyOwnedByYou:
    print(f"Bucket already exists: {bucket}")
except Exception as e:
    print(f"Bucket creation skipped: {e}")
