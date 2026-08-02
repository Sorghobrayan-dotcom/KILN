"""A two-method blob seam.

Production is Backblaze B2 through its S3-compatible API, so Kiln's own state
and Genblaze's assets land in exactly one place. Tests use the memory
implementation and never touch a network.
"""
from typing import Protocol


class Blobs(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def keys(self, prefix: str = "") -> list[str]: ...


class MemoryBlobs:
    def __init__(self) -> None:
        self._d: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._d[key] = data

    def get(self, key: str) -> bytes | None:
        return self._d.get(key)

    def keys(self, prefix: str = "") -> list[str]:
        return [k for k in self._d if k.startswith(prefix)]


class B2Blobs:
    def __init__(self, bucket: str, key_id: str, app_key: str, endpoint: str) -> None:
        import boto3

        self._c = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=app_key,
        )
        self._b = bucket

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._c.put_object(Bucket=self._b, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        try:
            return self._c.get_object(Bucket=self._b, Key=key)["Body"].read()
        except ClientError:
            return None

    def keys(self, prefix: str = "") -> list[str]:
        out: list[str] = []
        for page in self._c.get_paginator("list_objects_v2").paginate(Bucket=self._b, Prefix=prefix):
            out.extend(o["Key"] for o in page.get("Contents", []))
        return out
