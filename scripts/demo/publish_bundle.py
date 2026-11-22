"""(Chủ dự án) Đưa một bundle đã import (data/inbox/<run_id>/) lên HF Hub dataset private cho demo/web.

    conda run -n research python scripts/demo/publish_bundle.py <run_id>    # env nào có huggingface_hub + token đều được

Chỉ upload các part + bundle_manifest.json (đúng định dạng make_bundle), không upload silver/gold.
"""

from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import HfApi

HF_REPO = "paingoat/steam-rec-demo"
ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    run_id = sys.argv[1]
    src = ROOT / "data" / "inbox" / run_id
    if not (src / "bundle_manifest.json").exists():
        raise SystemExit(f"{src} has no bundle_manifest.json")
    api = HfApi()
    api.create_repo(HF_REPO, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(repo_id=HF_REPO, repo_type="dataset", folder_path=str(src), path_in_repo=f"bundles/{run_id}",
                      allow_patterns=["*.tar.part*", "bundle_manifest.json"], commit_message=f"Add bundle {run_id}")
    print(f"https://huggingface.co/datasets/{HF_REPO}/tree/main/bundles/{run_id}")


if __name__ == "__main__":
    main()
