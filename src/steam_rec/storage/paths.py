"""Single source of truth for lake key layout (see plan §5)."""

from __future__ import annotations


def bronze_prefix(version: int, ingest_run_id: str) -> str:
    return f"bronze/kaggle/v{version}/{ingest_run_id}"


def bronze_raw(version: int, ingest_run_id: str, filename: str) -> str:
    return f"{bronze_prefix(version, ingest_run_id)}/raw/{filename}"


def bronze_manifest(version: int, ingest_run_id: str) -> str:
    return f"{bronze_prefix(version, ingest_run_id)}/_manifest.json"


def bronze_latest(version: int) -> str:
    return f"bronze/kaggle/v{version}/_LATEST"


def bronze_meta_prefix(source: str, tag: str) -> str:
    """Game-metadata enrichment sources (hf, steamspy): bronze/game_meta/<source>-<tag>/{raw/,_manifest.json}."""
    return f"bronze/game_meta/{source}-{tag}"


def bronze_meta_latest() -> str:
    """JSON {source: tag} of the snapshots silver should use."""
    return "bronze/game_meta/_LATEST.json"


def silver(table: str, version: int, run_id: str) -> str:
    return f"silver/{table}/dataset=v{version}/run={run_id}"


def gold(table: str, version: int, run_id: str) -> str:
    return f"gold/{table}/dataset=v{version}/run={run_id}"


def artifacts(run_id: str, *parts: str) -> str:
    return "/".join([f"artifacts/{run_id}", *parts])


def success_marker(prefix: str) -> str:
    return f"{prefix.rstrip('/')}/_SUCCESS"
