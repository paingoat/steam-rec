# Runs INSIDE the Colab kernel (foreground!) via:
#   colab exec -s steam-rec-mvp --timeout 5400 --env STAGES=silver,gold --env SCALE=full --env RUN_ID=<id> \
#       -f scripts/colab/run_stage.py
# Env: STAGES (comma list incl. 'ingest', 'export'), SCALE, RUN_ID (required except for ingest).
# Each stage: restore lake from Drive (if VM was reset) -> run (skips if done) -> mirror lake to Drive.
import json
import os
import sys
from pathlib import Path

ROOT = "/content/steam_rec"
sys.path.insert(0, ROOT + "/src")
os.environ.setdefault("STEAM_REC_GIT_SHA", Path(f"{ROOT}/.src_sha").read_text().strip())
os.chdir(ROOT)

from pathlib import Path

from steam_rec.common.config import load_config
from steam_rec.common.logging import LOG, setup_logging
from steam_rec.storage.sync import mirror

setup_logging()
SCALE = os.environ.get("SCALE", "full")
STAGES = [s for s in os.environ["STAGES"].split(",") if s]
RUN_ID = os.environ.get("RUN_ID", "")
cfg = load_config("colab", SCALE)
LAKE = Path(cfg.storage.local_root)
DRIVE = Path(cfg.storage.checkpoint_root)
if not DRIVE.parent.exists():
    raise SystemExit(f"Drive not mounted ({DRIVE.parent}). Ask the user to run: colab drivemount -s <session>")

# size Spark to the VM (≈70% RAM for the driver in local[*] mode)
ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
os.environ.setdefault("STEAM_REC_DRIVER_MEMORY", f"{int(ram_gb * 0.7)}g")
os.environ.setdefault("STEAM_REC_SHUFFLE_PARTITIONS", str(max(16, (os.cpu_count() or 2) * 8)))
LOG.info("VM ram=%.1fGB cpus=%s driver=%s", ram_gb, os.cpu_count(), os.environ["STEAM_REC_DRIVER_MEMORY"])


def drive_run(rid):
    return DRIVE / rid


def restore(rid):
    """After a VM reset /content is empty: pull this run's checkpoints (silver/gold/artifacts) back from Drive."""
    src = drive_run(rid) / "lake"
    if src.exists() and not (LAKE / "artifacts" / rid).exists():
        LOG.info("restoring checkpoints from Drive for %s", rid)
        mirror(src, LAKE)


def checkpoint(rid):
    for sub in ("silver", "gold", f"artifacts/{rid}"):
        for p in (LAKE / sub).rglob(f"run={rid}") if sub in ("silver", "gold") else [LAKE / sub]:
            mirror(p, drive_run(rid) / "lake" / p.relative_to(LAKE), delete=sub.startswith("artifacts/"))


from steam_rec.cli import _ctx, _stage_fn
from steam_rec.pipelines.runner import run_stage

for stage in STAGES:
    if stage == "ingest":
        # Same pinned Kaggle version, downloaded on the VM; verified against the local Bronze manifest.
        from steam_rec.ingestion.kaggle import ingest, verify_against_manifest
        from steam_rec.storage.store import get_store

        m = ingest(cfg, get_store(cfg))
        local_manifest = json.loads(Path("/content/bronze_manifest_local.json").read_text())
        raw = LAKE / "bronze" / f"kaggle/v{cfg.dataset.version}/{m['ingest_run_id']}/raw"
        bad = verify_against_manifest(raw, local_manifest)
        if bad:
            raise SystemExit(f"Bronze on Colab differs from local Bronze: {bad}")
        LOG.info("✅ Colab Bronze matches local manifest (sha256) for %s", [f["name"] for f in m["files"]])
        continue
    if not RUN_ID:
        raise SystemExit("RUN_ID env is required for pipeline stages")
    restore(RUN_ID)
    if stage == "export":
        import shutil
        import tempfile

        from steam_rec.storage.bundle import make_bundle

        art = LAKE / "artifacts" / RUN_ID
        export_dir = Path("/content/export") / RUN_ID
        shutil.rmtree(export_dir, ignore_errors=True)
        with tempfile.TemporaryDirectory() as tmp:
            stage_dir = Path(tmp) / RUN_ID
            models_dir = art / "models"
            # serving bundle: full Spark ALS models (user factors, ~0.4 GB+) stay on Drive; serving needs item factors
            shutil.copytree(art, stage_dir,
                            ignore=lambda d, _n, md=models_dir: ["als", "als_trials"] if Path(d) == md else [])
            man = make_bundle(stage_dir, export_dir, RUN_ID, chunk_mb=45,
                              meta={"run_id": RUN_ID, "git_sha": os.environ["STEAM_REC_GIT_SHA"]})
        mirror(export_dir, drive_run(RUN_ID) / "bundle", delete=True)
        print(json.dumps({"bundle_dir": str(export_dir), "parts": len(man["parts"]),
                          "tar_mb": round(man["tar_size"] / 1e6, 1)}))
        continue
    ctx = _ctx("colab", SCALE, RUN_ID)
    res = run_stage(ctx, stage, _stage_fn(stage))
    checkpoint(RUN_ID)
    status = "incomplete" if "incomplete" in res else "done"
    print(json.dumps({"stage": stage, "run_id": RUN_ID, "status": status, "detail": res.get("incomplete")}))
    if status != "done":
        break  # later stages depend on this one
