"""S3-compatible file store client. B1 only makes sure the two buckets exist."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from core.config import get_settings
from core.logging import get_logger

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

log = get_logger("attachments.store")


def client() -> S3Client:
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def ensure_buckets(wait_seconds: float = 30.0) -> bool:
    s = get_settings()
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            c = client()
            existing = {b["Name"] for b in c.list_buckets().get("Buckets", [])}
            for bucket in (s.s3_bucket_quarantine, s.s3_bucket_clean):
                if bucket not in existing:
                    c.create_bucket(Bucket=bucket)
                    log.info("store.bucket_created", bucket=bucket)
            return True
        except (BotoCoreError, ClientError) as exc:
            if time.monotonic() > deadline:
                log.error("store.unavailable", error_type=type(exc).__name__)
                return False
            time.sleep(2)
