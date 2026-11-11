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


@app.command("eda")
def eda_cmd(env: str = EnvOpt, scale: str = typer.Option("full", "--scale")) -> None:
    """M3: EDA over the latest Bronze snapshot -> reports/eda/eda_summary.json"""
    from steam_rec.pipelines.eda import run_eda
    from steam_rec.storage.store import get_store

    cfg = load_config(env, scale)
    rep = run_eda(cfg, get_store(cfg))
    typer.echo(json.dumps(rep["rows"]))


STAGES = ["silver", "gold", "train", "evaluate", "recommend"]
StagesArg = typer.Argument(..., help=f"one or more of {STAGES} or 'all'")


def _ctx(env: str, scale: str, run_id: str | None):
    from steam_rec.common.run_id import new_run_id
    from steam_rec.pipelines.runner import Ctx
    from steam_rec.storage.store import get_store

    cfg = load_config(env, scale)
    rid = run_id or new_run_id(cfg.config_hash())
    LOG.info("run_id=%s env=%s scale=%s", rid, env, scale)
    return Ctx(cfg, get_store(cfg), rid)


def _stage_fn(name: str):
    from steam_rec.pipelines import gold, modeling, silver

    return {"silver": silver.run_silver, "gold": gold.run_gold, "train": modeling.run_train,
            "evaluate": modeling.run_evaluate, "recommend": modeling.run_recommend}[name]


@app.command("run")
def run_cmd(
    stages: list[str] = StagesArg,
    env: str = EnvOpt, scale: str = ScaleOpt,
    run_id: str = typer.Option(None, "--run-id", help="resume/extend an existing run"),
    force: bool = typer.Option(False, "--force", help="recompute stages even if already done"),
) -> None:
    """Run pipeline stages (idempotent per run_id; finished stages are skipped)."""
    from steam_rec.pipelines.runner import run_stage

    names = STAGES if stages == ["all"] else stages
    bad = [s for s in names if s not in STAGES]
    if bad:
        raise typer.BadParameter(f"unknown stages {bad}")
    ctx = _ctx(env, scale, run_id)
    for name in names:
        run_stage(ctx, name, _stage_fn(name), force=force)
    typer.echo(json.dumps({"run_id": ctx.run_id, "stages": names}))


@app.command("demo")
def demo_cmd(
    user_id: int = typer.Option(None, "--user-id"),
    tags: str = typer.Option(None, "--tags", help="cold-start: comma-separated tags, e.g. 'RPG,Indie'"),
    model: str = typer.Option("als", "--model", help="als | cb | popularity"),
    k: int = typer.Option(10, "-k"),
    run_id: str = typer.Option(None, "--run-id"),
    env: str = EnvOpt,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Offline recommendations from precomputed artifacts (works with Colab off)."""
    from steam_rec.serving.demo import Demo, pretty
    from steam_rec.storage.store import get_store

    cfg = load_config(env)
    d = Demo(cfg, get_store(cfg), run_id, k)
    if user_id is None and not tags:
        raise typer.BadParameter("give --user-id or --tags")
    res = d.for_user(user_id, model) if user_id is not None else d.for_new_user(tags.split(","))
    typer.echo(json.dumps(res, default=str, ensure_ascii=False, indent=2) if as_json else pretty(res))


@app.command("show-config")
def show_config(env: str = EnvOpt, scale: str = ScaleOpt) -> None:
    cfg = load_config(env, scale)
    typer.echo(json.dumps({"config_hash": cfg.config_hash(), **cfg.model_dump(mode="json")}, indent=2))


if __name__ == "__main__":
    app()
