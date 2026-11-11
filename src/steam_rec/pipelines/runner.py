"""Stage context + idempotency. A stage is done iff artifacts/<run_id>/stages/<stage>.json exists."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import yaml

from steam_rec.common.config import Config
from steam_rec.common.logging import LOG
from steam_rec.common.run_id import git_commit, utc_now
from steam_rec.storage import paths
from steam_rec.storage.store import Store


@dataclass
class Ctx:
    cfg: Config
    store: Store
    run_id: str
    _spark: object = field(default=None, repr=False)

    @property
    def v(self) -> int:
        return self.cfg.dataset.version

    @property
    def spark(self):
        if self._spark is None:
            from steam_rec.common.spark import get_spark

            self._spark = get_spark(self.cfg, f"steam-rec-{self.run_id}")
        return self._spark

    def uri(self, key: str) -> str:
        return self.store.uri(key)

    def silver(self, table: str) -> str:
        return paths.silver(table, self.v, self.run_id)

    def gold(self, table: str) -> str:
        return paths.gold(table, self.v, self.run_id)

    def art(self, *parts: str) -> str:
        return paths.artifacts(self.run_id, *parts)

    def read(self, key: str):
        return self.spark.read.parquet(self.uri(key))

    def write(self, df, key: str, partition_by: list[str] | None = None) -> None:
        w = df.write.mode("overwrite")
        if partition_by:
            w = w.partitionBy(*partition_by)
        w.parquet(self.uri(key))

    def put_json(self, key: str, obj) -> None:
        self.store.put_text(key, json.dumps(obj, indent=2, default=str))

    def get_json(self, key: str):
        return json.loads(self.store.get_text(key))


def stage_marker(ctx: Ctx, name: str) -> str:
    return ctx.art("stages", f"{name}.json")


def write_run_meta(ctx: Ctx) -> None:
    key = ctx.art("config.resolved.yaml")
    if not ctx.store.exists(key):
        ctx.store.put_text(key, yaml.safe_dump(ctx.cfg.model_dump(mode="json"), sort_keys=False))
        ctx.put_json(ctx.art("run.json"), {"run_id": ctx.run_id, "git_commit": git_commit(), "created_at": utc_now(),
                                          "config_hash": ctx.cfg.config_hash(), "execution": ctx.cfg.execution,
                                          "scale": ctx.cfg.scale.name})


def run_stage(ctx: Ctx, name: str, fn: Callable[[Ctx], dict], force: bool = False) -> dict:
    marker = stage_marker(ctx, name)
    if not force and ctx.store.exists(marker):
        LOG.info("⏭ stage %s already done for %s (use --force to recompute)", name, ctx.run_id)
        return ctx.get_json(marker)
    write_run_meta(ctx)
    t0 = utc_now()
    metrics = fn(ctx) or {}
    out = {"stage": name, "run_id": ctx.run_id, "git_commit": git_commit(), "started_at": t0,
           "finished_at": utc_now(), "elapsed_s": round((utc_now() - t0).total_seconds(), 1), "metrics": metrics}
    ctx.put_json(marker, out)
    LOG.info("✅ stage %s done in %ss", name, out["elapsed_s"])
    return out
