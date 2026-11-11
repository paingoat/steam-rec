"""Object store abstraction: SILO (S3 API via boto3) or local filesystem. Keys are '/'-separated."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Protocol

from steam_rec.common.config import Config, s3_settings


def sha256_file(path: Path, bufsize: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(bufsize):
            h.update(chunk)
    return h.hexdigest()


class Store(Protocol):
    def uri(self, key: str) -> str: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> list[str]: ...
    def put_file(self, local: Path, key: str) -> None: ...
    def get_file(self, key: str, local: Path) -> None: ...
    def put_text(self, key: str, text: str) -> None: ...
    def get_text(self, key: str) -> str: ...


class LocalStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _p(self, key: str) -> Path:
        return self.root / key

    def uri(self, key: str) -> str:
        return self._p(key).as_uri()

    def exists(self, key: str) -> bool:
        return self._p(key).exists()

    def list(self, prefix: str) -> list[str]:
        base = self._p(prefix)
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file())

    def put_file(self, local: Path, key: str) -> None:
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local, dst)

    def get_file(self, key: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._p(key), local)

    def put_text(self, key: str, text: str) -> None:
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)

    def get_text(self, key: str) -> str:
        return self._p(key).read_text()


class S3Store:
    def __init__(self, bucket: str):
        import boto3
        from botocore.config import Config as BotoConfig

        s = s3_settings()
        self.bucket = bucket
        self.endpoint = s["endpoint"]
        self.client = boto3.client(
            "s3", endpoint_url=s["endpoint"], aws_access_key_id=s["access_key"],
            aws_secret_access_key=s["secret_key"], region_name="us-east-1",
            config=BotoConfig(s3={"addressing_style": "path"}, retries={"max_attempts": 5, "mode": "standard"}),
        )

    def ensure_bucket(self) -> bool:
        """Create bucket if missing. Returns True if created."""
        names = {b["Name"] for b in self.client.list_buckets().get("Buckets", [])}
        if self.bucket in names:
            return False
        self.client.create_bucket(Bucket=self.bucket)
        return True

    def uri(self, key: str) -> str:
        return f"s3a://{self.bucket}/{key}"

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            # treat as "directory" prefix if any object lives under it
            resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=key.rstrip("/") + "/", MaxKeys=1)
            return resp.get("KeyCount", 0) > 0

    def list(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys += [o["Key"] for o in page.get("Contents", [])]
        return sorted(keys)

    def put_file(self, local: Path, key: str) -> None:
        self.client.upload_file(str(local), self.bucket, key)

    def get_file(self, key: str, local: Path) -> None:
        local.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(local))

    def put_text(self, key: str, text: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=text.encode())

    def get_text(self, key: str) -> str:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read().decode()


def get_store(cfg: Config) -> Store:
    if cfg.storage.backend == "s3":
        return S3Store(cfg.storage.bucket)
    return LocalStore(cfg.resolve_path(cfg.storage.local_root))
