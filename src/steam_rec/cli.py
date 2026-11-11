"""steam-rec CLI: same entrypoints on local and Colab (only --env changes)."""

from __future__ import annotations

import json

import typer

from steam_rec.common.config import load_config
from steam_rec.common.logging import LOG, setup_logging

app = typer.Typer(no_args_is_help=True, add_completion=False)
storage_app = typer.Typer(no_args_is_help=True)
app.add_typer(storage_app, name="storage")

EnvOpt = typer.Option("local", "--env", help="local | colab")
ScaleOpt = typer.Option("smoke", "--scale", help="smoke | dev | full")


@app.callback()
def _main(log_level: str = typer.Option("INFO", "--log-level")) -> None:
    setup_logging(log_level)


@storage_app.command("init")
def storage_init(env: str = EnvOpt) -> None:
    """Create the lake bucket (S3) or root directory (local)."""
    from steam_rec.storage.store import S3Store, get_store

    cfg = load_config(env)
    store = get_store(cfg)
    if isinstance(store, S3Store):
        created = store.ensure_bucket()
        LOG.info("bucket %s %s at %s", cfg.storage.bucket, "created" if created else "exists", store.endpoint)
    else:
        store.root.mkdir(parents=True, exist_ok=True)
        LOG.info("local lake root %s", store.root)


@app.command("ingest")
def ingest_cmd(env: str = EnvOpt, raw_dir: str = typer.Option(None, help="use already-downloaded files")) -> None:
    """Download pinned Kaggle version and publish an immutable Bronze snapshot (+manifest)."""
    from pathlib import Path

    from steam_rec.ingestion.kaggle import ingest
    from steam_rec.storage.store import get_store

    cfg = load_config(env)
    m = ingest(cfg, get_store(cfg), Path(raw_dir) if raw_dir else None)
    typer.echo(json.dumps({"ingest_run_id": m["ingest_run_id"], "files": [(f["name"], f["size"]) for f in m["files"]]}))


@app.command("show-config")
def show_config(env: str = EnvOpt, scale: str = ScaleOpt) -> None:
    cfg = load_config(env, scale)
    typer.echo(json.dumps({"config_hash": cfg.config_hash(), **cfg.model_dump(mode="json")}, indent=2))


if __name__ == "__main__":
    app()
