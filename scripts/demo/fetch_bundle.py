"""Kéo bundle artifacts của một run từ HF Hub (dataset public) và import vào lake local của env 'demo'.

Chạy từ gốc repo (repo HF là public, không cần token):
    uv run --with huggingface_hub python scripts/demo/fetch_bundle.py            # run mới nhất trên HF
    uv run --with huggingface_hub python scripts/demo/fetch_bundle.py --run-id <run_id>

Bundle giữ nguyên định dạng của pipeline (tar chunk + bundle_manifest.json), nên import đi qua
steam_rec.storage.importer.import_bundle (kiểm tra SHA-256 từng part, cả tar và từng file).
Chạy lại là an toàn: file đã tải sẽ được dùng lại, import ghi đè cùng nội dung.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

from steam_rec.common.config import REPO_ROOT, load_config
from steam_rec.common.logging import setup_logging
from steam_rec.storage.importer import import_bundle
from steam_rec.storage.store import get_store

HF_REPO = "paingoat/steam-rec-demo"


def latest_run_id(repo: str) -> str:
    runs = sorted(e.path.split("/")[1] for e in HfApi().list_repo_tree(repo, repo_type="dataset", path_in_repo="bundles"))
    if not runs:
        raise SystemExit(f"no bundles/ in {repo}")
    return runs[-1]  # run_id bắt đầu bằng timestamp UTC -> sort chữ = sort thời gian


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=HF_REPO)
    ap.add_argument("--run-id", default=None, help="mặc định: run mới nhất trong bundles/")
    ap.add_argument("--env", default="demo", help="env config để import vào (mặc định demo = data/lake)")
    a = ap.parse_args()
    setup_logging()

    run_id = a.run_id or latest_run_id(a.repo)
    inbox = REPO_ROOT / "data" / "inbox"
    snapshot_download(a.repo, repo_type="dataset", allow_patterns=[f"bundles/{run_id}/*"], local_dir=inbox / "_hf")
    bundle_dir = inbox / "_hf" / "bundles" / run_id
    if not (bundle_dir / "bundle_manifest.json").exists():
        raise SystemExit(f"bundle {run_id} not found in {a.repo}")

    cfg = load_config(a.env)
    res = import_bundle(Path(bundle_dir), get_store(cfg))
    print(json.dumps({**res, "env": a.env, "lake": cfg.storage.local_root if cfg.storage.backend == "local"
                      else f"s3://{cfg.storage.bucket}"}))


if __name__ == "__main__":
    main()
