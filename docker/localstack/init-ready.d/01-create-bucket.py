#!/usr/bin/env python3
"""Create the default S3 bucket and the performances bucket when LocalStack is ready."""

import os

import boto3

PERFORMANCES_BUCKET_NAME = "performances"

bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME", "eu-fact-force")
region = os.environ.get("AWS_S3_REGION_NAME", "eu-west-1")

client = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    region_name=region,
)

for name in (bucket, PERFORMANCES_BUCKET_NAME):
    try:
        client.create_bucket(Bucket=name)
        print(f"Created bucket: {name}")
    except client.exceptions.BucketAlreadyOwnedByYou:
        print(f"Bucket already exists: {name}")
    except Exception as e:
        print(f"Bucket creation skipped for {name}: {e}")
