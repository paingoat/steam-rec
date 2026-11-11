"""Read the latest (or given) Bronze snapshot with explicit schemas. PERMISSIVE parsing + corrupt-row column."""

from __future__ import annotations

import json

from pyspark.sql import DataFrame, SparkSession

from steam_rec.common import schemas
from steam_rec.common.config import Config
from steam_rec.storage import paths
from steam_rec.storage.store import Store


def bronze_manifest(cfg: Config, store: Store, ingest_run_id: str | None = None) -> dict:
    v = cfg.dataset.version
    run = ingest_run_id or store.get_text(paths.bronze_latest(v)).strip()
    return json.loads(store.get_text(paths.bronze_manifest(v, run)))


def read_bronze(spark: SparkSession, cfg: Config, store: Store, manifest: dict) -> dict[str, DataFrame]:
    v, run = cfg.dataset.version, manifest["ingest_run_id"]
    uri = lambda f: store.uri(paths.bronze_raw(v, run, f))
    csv = spark.read.option("header", True).option("mode", "PERMISSIVE")
    return {
        "games": csv.schema(schemas.GAMES).csv(uri("games.csv")),
        "users": csv.schema(schemas.USERS).csv(uri("users.csv")),
        "recommendations": csv.schema(schemas.RECOMMENDATIONS).csv(uri("recommendations.csv")),
        "games_metadata": spark.read.json(uri("games_metadata.json")),
    }
