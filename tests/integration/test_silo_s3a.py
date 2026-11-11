"""Needs SILO running (docker compose -f infra/silo/docker-compose.yml up -d). Run: pytest -m integration"""

import pytest

from steam_rec.common.config import load_config
from steam_rec.common.spark import get_spark
from steam_rec.storage.store import S3Store

pytestmark = pytest.mark.integration


def test_boto3_and_s3a_roundtrip():
    cfg = load_config("local", "smoke")
    store = S3Store(cfg.storage.bucket)
    store.ensure_bucket()
    store.put_text("_healthcheck/ping.txt", "pong")
    assert store.get_text("_healthcheck/ping.txt") == "pong"

    spark = get_spark(cfg, "s3a-test")
    uri = store.uri("_healthcheck/parquet")
    spark.range(1000).withColumnRenamed("id", "x").write.mode("overwrite").parquet(uri)
    assert spark.read.parquet(uri).count() == 1000
