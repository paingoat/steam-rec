"""Typed config: base.yaml <- {env}.yaml <- scale/{scale}.yaml <- CLI overrides; secrets from env/.env."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "configs"


class DatasetCfg(BaseModel):
    kaggle_handle: str
    version: int
    files: list[str]


class StorageCfg(BaseModel):
    backend: Literal["s3", "local"] = "s3"
    bucket: str = "steam-rec"
    local_root: str = "data/lake"
    staging_dir: str = "data/staging"
    checkpoint_root: str | None = None


class SparkCfg(BaseModel):
    master: str = "local[8]"
    driver_memory: str = "4g"
    shuffle_partitions: int = 16
    local_dir: str = "data/spark-tmp"
    checkpoint_dir: str = "data/spark-checkpoint"
    hadoop_aws_version: str = "3.4.1"


class ScaleCfg(BaseModel):
    name: str = "smoke"
    max_recommendations: int | None = 100_000
    sample_seed: int = 42


class EvalCfg(BaseModel):
    k_values: list[int] = Field(default_factory=lambda: [10, 20])
    max_eval_users: int = 100_000


class Config(BaseModel):
    execution: Literal["local", "colab"] = "local"
    dataset: DatasetCfg
    storage: StorageCfg = StorageCfg()
    spark: SparkCfg = SparkCfg()
    scale: ScaleCfg = ScaleCfg()
    eval: EvalCfg = EvalCfg()
    model: dict[str, Any] = Field(default_factory=dict)

    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()[:8]

    def resolve_path(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else REPO_ROOT / path


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {} if path.exists() else {}


def load_config(env: str = "local", scale: str = "smoke", overrides: dict | None = None,
                config_dir: Path = CONFIG_DIR) -> Config:
    raw = _read(config_dir / "base.yaml")
    raw = deep_merge(raw, _read(config_dir / f"{env}.yaml"))
    raw = deep_merge(raw, _read(config_dir / "scale" / f"{scale}.yaml"))
    models: dict[str, Any] = {}
    for f in sorted((config_dir / "models").glob("*.yaml")):
        models[f.stem] = _read(f)
    raw["model"] = deep_merge(models, raw.get("model", {}))
    raw = deep_merge(raw, overrides or {})
    return Config.model_validate(raw)


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (no override of existing env vars)."""
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def s3_settings() -> dict[str, str]:
    load_dotenv()
    return {
        "endpoint": os.environ.get("S3_ENDPOINT", "http://127.0.0.1:9000"),
        "access_key": os.environ.get("S3_ACCESS_KEY", ""),
        "secret_key": os.environ.get("S3_SECRET_KEY", ""),
    }
