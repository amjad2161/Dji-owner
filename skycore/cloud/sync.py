"""S3-compatible cloud sync for drone footage and logs.

Works with AWS S3, MinIO, Backblaze B2 (S3 mode), Cloudflare R2, or any
S3-API service. Uploads happen in the background so flight operations
aren't blocked.
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class S3Sync:
    bucket: str
    region: str = "us-east-1"
    endpoint_url: Optional[str] = None  # for MinIO/R2/etc
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    prefix: str = ""  # e.g. "flights/2026-05/"

    def __post_init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as e:
            raise ImportError("boto3 is required. pip install boto3") from e
        kwargs = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key:
            kwargs["aws_access_key_id"] = self.access_key
            kwargs["aws_secret_access_key"] = self.secret_key
        self._client = boto3.client("s3", **kwargs)
        return self._client

    async def upload_file(self, local_path: Path | str, key: Optional[str] = None) -> str:
        """Upload one file to S3. Returns the full key written."""
        p = Path(local_path)
        if not p.exists():
            raise FileNotFoundError(p)
        full_key = (self.prefix + (key or p.name)).lstrip("/")
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        loop = asyncio.get_running_loop()

        def _do():
            client = self._ensure_client()
            client.upload_file(
                str(p), self.bucket, full_key,
                ExtraArgs={"ContentType": ctype},
            )
            return full_key

        return await loop.run_in_executor(None, _do)

    async def upload_directory(self, local_dir: Path | str, key_prefix: str = "") -> list[str]:
        """Upload every file in a directory tree."""
        d = Path(local_dir)
        if not d.exists():
            raise FileNotFoundError(d)
        keys: list[str] = []
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(d).as_posix()
            keys.append(await self.upload_file(f, key=f"{key_prefix.rstrip('/')}/{rel}".lstrip("/")))
        return keys

    async def list_keys(self, prefix: str = "") -> list[str]:
        loop = asyncio.get_running_loop()

        def _do():
            client = self._ensure_client()
            full_prefix = self.prefix + prefix
            keys = []
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []) or []:
                    keys.append(obj["Key"])
            return keys

        return await loop.run_in_executor(None, _do)

    async def presigned_url(self, key: str, expires_s: int = 3600) -> str:
        loop = asyncio.get_running_loop()

        def _do():
            client = self._ensure_client()
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": (self.prefix + key).lstrip("/")},
                ExpiresIn=expires_s,
            )

        return await loop.run_in_executor(None, _do)
