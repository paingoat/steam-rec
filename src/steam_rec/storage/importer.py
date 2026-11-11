"""Local side of M6: verify a downloaded Colab bundle (per-part + whole-tar + per-file SHA-256) and import it
into the lake under artifacts/<run_id>/ (Spark-free; files are copied as-is)."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from steam_rec.common.logging import LOG
from steam_rec.storage import paths
from steam_rec.storage.bundle import MANIFEST, restore_bundle, verify_parts
from steam_rec.storage.store import Store


def import_bundle(bundle_dir: Path, store: Store) -> dict:
    bundle_dir = Path(bundle_dir)
    m = json.loads((bundle_dir / MANIFEST).read_text())
    run_id = m["meta"]["run_id"]
    if bad := verify_parts(bundle_dir):
        raise SystemExit(f"missing/corrupt parts (re-download only these): {bad}")
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / run_id
        restore_bundle(bundle_dir, dest)  # raises on any tar/file checksum mismatch
        n = 0
        for f in sorted(p for p in dest.rglob("*") if p.is_file()):
            store.put_file(f, paths.artifacts(run_id, str(f.relative_to(dest))))
            n += 1
    store.put_text(paths.artifacts(run_id, "_IMPORTED.json"),
                   json.dumps({"bundle": m["name"], "tar_sha256": m["tar_sha256"], "files": n, **m["meta"]}))
    LOG.info("imported %s files for %s into the lake", n, run_id)
    return {"run_id": run_id, "files": n, "tar_mb": round(m["tar_size"] / 1e6, 1)}


def remove_local_bundle(bundle_dir: Path) -> None:
    shutil.rmtree(bundle_dir, ignore_errors=True)
