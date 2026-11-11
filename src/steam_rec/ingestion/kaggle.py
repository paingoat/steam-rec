"""Kaggle → Bronze. Pinned dataset version, SHA-256 manifest, idempotent (same checksums ⇒ no new snapshot)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from steam_rec.common.config import Config
from steam_rec.common.logging import LOG, phase
from steam_rec.common.run_id import utc_now
from steam_rec.storage import paths
from steam_rec.storage.store import Store, sha256_file


def download(cfg: Config, staging: Path | None = None) -> Path:
    """Download + extract the pinned version. Returns the directory holding the raw files."""
    import kagglehub

    ds = cfg.dataset
    handle = f"{ds.kaggle_handle}/versions/{ds.version}"
    if staging is not None:
        os.environ["KAGGLEHUB_CACHE"] = str(staging)
    with phase("kaggle.download", handle=handle):
        path = Path(kagglehub.dataset_download(handle))
    missing = [f for f in ds.files if not (path / f).exists()]
    if missing:
        raise FileNotFoundError(f"expected files missing after download: {missing} in {path}")
    return path


def build_file_entries(raw_dir: Path, files: list[str]) -> list[dict]:
    return [{"name": f, "size": (raw_dir / f).stat().st_size, "sha256": sha256_file(raw_dir / f)} for f in files]


def verify_against_manifest(raw_dir: Path, manifest: dict) -> list[str]:
    """Return list of mismatching files (empty == identical to Bronze)."""
    bad = []
    for fe in manifest["files"]:
        p = raw_dir / fe["name"]
        if not p.exists() or p.stat().st_size != fe["size"] or sha256_file(p) != fe["sha256"]:
            bad.append(fe["name"])
    return bad


def latest_manifest(store: Store, version: int) -> dict | None:
    key = paths.bronze_latest(version)
    if not store.exists(key):
        return None
    run = store.get_text(key).strip()
    return json.loads(store.get_text(paths.bronze_manifest(version, run)))


def ingest(cfg: Config, store: Store, raw_dir: Path | None = None) -> dict:
    ds = cfg.dataset
    raw_dir = raw_dir or download(cfg, cfg.resolve_path(cfg.storage.staging_dir) / "kagglehub")
    with phase("bronze.checksum") as m:
        entries = build_file_entries(raw_dir, ds.files)
        m["bytes"] = sum(e["size"] for e in entries)

    prev = latest_manifest(store, ds.version)
    same = prev and {e["name"]: e["sha256"] for e in prev["files"]} == {e["name"]: e["sha256"] for e in entries}
    if same and all(store.exists(paths.bronze_raw(ds.version, prev["ingest_run_id"], e["name"])) for e in entries):
        LOG.info("bronze snapshot %s already has identical files → no-op", prev["ingest_run_id"])
        return prev

    now = utc_now()
    run = f"{now:%Y%m%dT%H%M%SZ}"
    with phase("bronze.upload", run=run):
        for e in entries:
            key = paths.bronze_raw(ds.version, run, e["name"])
            store.put_file(raw_dir / e["name"], key)
            e["key"] = key
    manifest = {
        "source": "kaggle",
        "kaggle_handle": ds.kaggle_handle,
        "dataset_version": ds.version,
        "source_url": f"https://www.kaggle.com/datasets/{ds.kaggle_handle}/versions/{ds.version}",
        "ingest_run_id": run,
        "ingested_at": now.isoformat(),
        "files": entries,
    }
    # manifest + _LATEST written last: a snapshot only "exists" once fully uploaded
    store.put_text(paths.bronze_manifest(ds.version, run), json.dumps(manifest, indent=2))
    store.put_text(paths.bronze_latest(ds.version), run)
    LOG.info("bronze snapshot published: %s", paths.bronze_prefix(ds.version, run))
    return manifest
