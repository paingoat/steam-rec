from __future__ import annotations

import subprocess
from datetime import UTC, datetime

from steam_rec.common.config import REPO_ROOT


def git_commit(short: bool = True) -> str:
    """Commit of the code being run. On Colab the snapshot has no .git; bootstrap exports STEAM_REC_GIT_SHA."""
    import os

    if sha := os.environ.get("STEAM_REC_GIT_SHA"):
        return sha[:7] if short else sha
    try:
        args = ["git", "rev-parse", "--short" if short else "--verify", "HEAD"]
        sha = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO_ROOT,
                               capture_output=True, text=True, check=False).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "nogit"


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_run_id(config_hash: str, now: datetime | None = None) -> str:
    now = now or utc_now()
    return f"{now:%Y%m%dT%H%M%SZ}-{git_commit()}-{config_hash}"
