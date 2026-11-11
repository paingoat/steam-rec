"""Pack a directory into tar + fixed-size chunks with a SHA-256 manifest; verify and reassemble.

Used to move Colab outputs back to local in pieces that `colab download` handles reliably (≤45 MB).
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from steam_rec.storage.store import sha256_file

MANIFEST = "bundle_manifest.json"


def make_bundle(src_dir: Path, out_dir: Path, name: str, chunk_mb: int = 45, meta: dict | None = None) -> dict:
    src_dir, out_dir = Path(src_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    file_entries = [{"path": str(p.relative_to(src_dir)), "size": p.stat().st_size, "sha256": sha256_file(p)}
                    for p in files]
    tar_path = out_dir / f"{name}.tar"
    with tarfile.open(tar_path, "w") as tar:
        for p in files:
            tar.add(p, arcname=str(p.relative_to(src_dir)))
    chunk = chunk_mb * 1024 * 1024
    parts = []
    with open(tar_path, "rb") as f:
        i = 0
        while data := f.read(chunk):
            part = out_dir / f"{name}.tar.part{i:04d}"
            part.write_bytes(data)
            parts.append({"file": part.name, "size": len(data), "sha256": sha256_file(part)})
            i += 1
    manifest = {"name": name, "tar_sha256": sha256_file(tar_path), "tar_size": tar_path.stat().st_size,
                "parts": parts, "files": file_entries, "meta": meta or {}}
    tar_path.unlink()
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2))
    return manifest


def verify_parts(bundle_dir: Path) -> list[str]:
    """Return names of missing/corrupt parts (empty list == OK)."""
    m = json.loads((Path(bundle_dir) / MANIFEST).read_text())
    bad = []
    for p in m["parts"]:
        f = Path(bundle_dir) / p["file"]
        if not f.exists() or f.stat().st_size != p["size"] or sha256_file(f) != p["sha256"]:
            bad.append(p["file"])
    return bad


def restore_bundle(bundle_dir: Path, dest: Path) -> dict:
    bundle_dir, dest = Path(bundle_dir), Path(dest)
    if bad := verify_parts(bundle_dir):
        raise ValueError(f"corrupt/missing parts: {bad}")
    m = json.loads((bundle_dir / MANIFEST).read_text())
    tar_path = bundle_dir / f"{m['name']}.tar"
    with open(tar_path, "wb") as out:
        out.writelines((bundle_dir / p["file"]).read_bytes() for p in m["parts"])
    if sha256_file(tar_path) != m["tar_sha256"]:
        raise ValueError("reassembled tar checksum mismatch")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest, filter="data")
    tar_path.unlink()
    for fe in m["files"]:
        if sha256_file(dest / fe["path"]) != fe["sha256"]:
            raise ValueError(f"file checksum mismatch: {fe['path']}")
    return m
