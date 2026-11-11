"""Directory mirroring for Colab <-> Drive checkpoints (rsync if present, else size-based copy)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from steam_rec.common.logging import LOG


def mirror(src: Path, dst: Path) -> None:
    src, dst = Path(src), Path(dst)
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync"):
        subprocess.run(["rsync", "-a", f"{src}/", f"{dst}/"], check=True)
    else:
        for p in src.rglob("*"):
            if p.is_file():
                q = dst / p.relative_to(src)
                if not q.exists() or q.stat().st_size != p.stat().st_size:
                    q.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, q)
    LOG.info("mirrored %s -> %s", src, dst)
