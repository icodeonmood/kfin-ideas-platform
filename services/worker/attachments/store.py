"""S3-compatible file store client: the two buckets, and the quarantine bucket's backstop rule for voice notes.

Voice notes (DEC-096, BLD-C006): recordings live only under `voice/` in the quarantine bucket. A lifecycle rule
expires that prefix after 1 day, and the bucket must not be versioned (a version would outlive the delete). The
dev gateway may not support lifecycle rules: then the worker's own sweep deletes `voice/` objects older than 25
hours, and the UAT and prod buckets get the rule from IT (docs/UAT.md, RUNBOOK §2).
"""

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
            voice_lifecycle()
            return True
        except (BotoCoreError, ClientError) as exc:
            if time.monotonic() > deadline:
                log.error("store.unavailable", error_type=type(exc).__name__)
                return False
            time.sleep(2)


def put(bucket: str, key: str, data: bytes) -> None:
    client().put_object(Bucket=bucket, Key=key, Body=data)


def get(bucket: str, key: str) -> bytes:
    return client().get_object(Bucket=bucket, Key=key)["Body"].read()


def delete(bucket: str, key: str) -> None:
    client().delete_object(Bucket=bucket, Key=key)


def exists(bucket: str, key: str) -> bool:
    try:
        client().head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


VOICE_PREFIX = "voice/"
VOICE_RULE = {
    "ID": "voice-notes-expire-1-day",
    "Filter": {"Prefix": VOICE_PREFIX},
    "Status": "Enabled",
    "Expiration": {"Days": 1},
}


def voice_lifecycle() -> str:
    """Put the 1-day expiry on the quarantine bucket's `voice/` prefix, keeping any other rules there. Returns
    `set`, `present` or `unsupported` (the dev gateway); never raises, since the sweep is the backstop."""
    bucket = get_settings().s3_bucket_quarantine
    c = client()
    try:
        try:
            rules = c.get_bucket_lifecycle_configuration(Bucket=bucket).get("Rules", [])
        except ClientError:
            rules = []
        if any(r.get("ID") == VOICE_RULE["ID"] for r in rules):
            return "present"
        others = [r for r in rules if r.get("ID") != VOICE_RULE["ID"]]
        c.put_bucket_lifecycle_configuration(
            Bucket=bucket,
            LifecycleConfiguration={"Rules": [*others, VOICE_RULE]},  # type: ignore[list-item]
        )
        log.info("store.voice_lifecycle_set", bucket=bucket)
        return "set"
    except (BotoCoreError, ClientError) as exc:
        log.warning("store.voice_lifecycle_unsupported", bucket=bucket, error_type=type(exc).__name__)
        return "unsupported"


def versioning(bucket: str) -> str:
    """The bucket's versioning status: `Enabled`, `Suspended` or `never` (S3's answer has no Status then)."""
    return str(client().get_bucket_versioning(Bucket=bucket).get("Status") or "never")


def delete_older(bucket: str, prefix: str, age_s: float) -> int:
    """Delete every object under `prefix` last modified more than `age_s` ago. Returns how many."""
    import datetime as dt

    c = client()
    cutoff = dt.datetime.now(tz=dt.UTC) - dt.timedelta(seconds=age_s)
    done = 0
    for page in c.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["LastModified"] < cutoff:
                c.delete_object(Bucket=bucket, Key=obj["Key"])
                done += 1
    return done
