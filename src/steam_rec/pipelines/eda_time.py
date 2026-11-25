"""EDA for choosing the global temporal split (T_val, T_test).

Split under study (production-style, replaces per-user leave-last-out):
  train = positives with date < T_val  ->  k-core (min_user_pos / min_item_pos) on TRAIN ONLY
  val   = positives in [T_val, T_test) of train-core users on train-core items
  test  = positives in [T_test, end]   of train-core users on train-core items
For each candidate pair the report shows how much signal each side keeps, so the owner can pick the cut-off.
Only aggregates reach the driver."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import functions as F

from steam_rec.common.config import REPO_ROOT, Config
from steam_rec.common.logging import LOG, phase
from steam_rec.common.spark import get_spark
from steam_rec.features.cf_interactions import kcore
from steam_rec.pipelines.bronze_reader import bronze_manifest, read_bronze
from steam_rec.pipelines.silver import dedup_user_app
from steam_rec.storage.store import Store

CANDIDATES = [("2022-07-01", "2022-10-01"), ("2022-09-01", "2022-11-01"),
              ("2022-10-01", "2022-11-15"), ("2022-11-01", "2022-12-01")]
DATA_END = "2022-12-31"


def _window_stats(win, core_users, core_items, games, start: str) -> dict:
    """win: positives inside one window (user_id, app_id, date)."""
    tot = win.count()
    by_core_user = win.join(core_users, "user_id", "left_semi")
    warm = by_core_user.join(core_items, "app_id", "left_semi")
    n_cu, n_warm = by_core_user.count(), warm.count()
    per_user = warm.groupBy("user_id").count()
    q = per_user.agg(F.count("*").alias("users"), F.avg("count").alias("mean"),
                     F.expr("percentile(count, array(0.5, 0.9, 0.99))").alias("q")).first()
    new_games = win.join(games.filter(F.col("date_release") >= F.lit(start)).select("app_id"), "app_id",
                         "left_semi").count()
    return {
        "positives": tot,
        "positives_of_core_users": n_cu,
        "warm_targets": n_warm,  # core user AND core item -> scorable by every model
        "cold_item_share_of_core_user_targets": round(1 - n_warm / max(1, n_cu), 4),
        "eval_users": q["users"],
        "targets_per_user_mean": round(q["mean"] or 0, 3),
        "targets_per_user_p50_p90_p99": [round(x, 1) for x in (q["q"] or [])],
        "share_on_games_released_in_window": round(new_games / max(1, tot), 4),
    }


def run_eda_time(cfg: Config, store: Store, candidates=CANDIDATES, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or REPO_ROOT / "reports" / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)
    spark = get_spark(cfg, "eda-time")
    man = bronze_manifest(cfg, store)
    raw = read_bronze(spark, cfg, store, man)
    g = cfg.gold
    games = raw["games"].select("app_id", F.to_date("date_release").alias("date_release"))
    recs = dedup_user_app(raw["recommendations"].withColumn("date", F.to_date("date")))
    recs = recs.select("user_id", "app_id", "date", "is_recommended").persist(StorageLevel.MEMORY_AND_DISK)
    rep: dict = {"bronze_ingest_run_id": man["ingest_run_id"], "kcore": [g.min_user_pos, g.min_item_pos],
                 "data_end": DATA_END, "candidates": []}

    with phase("eda_time.monthly"):
        rows = (recs.filter(F.col("date") >= "2020-01-01").groupBy(F.date_format("date", "yyyy-MM").alias("m"))
                .agg(F.count("*").alias("reviews"), F.sum(F.col("is_recommended").cast("int")).alias("positives"),
                     F.countDistinct("user_id").alias("users"))
                .orderBy("m").collect())
        rep["monthly"] = [r.asDict() for r in rows]

    pos = recs.filter("is_recommended").drop("is_recommended")
    for t_val, t_test in candidates:
        with phase("eda_time.candidate", t_val=t_val, t_test=t_test) as pm:
            train = pos.filter(F.col("date") < t_val)
            core, rounds = kcore(train.select("user_id", "app_id"), g.min_user_pos, g.min_item_pos, g.kcore_max_rounds)
            core = core.persist(StorageLevel.MEMORY_AND_DISK)
            cu, ci = core.select("user_id").distinct(), core.select("app_id").distinct()
            st = {"t_val": t_val, "t_test": t_test,
                  "val_days": (dt.date.fromisoformat(t_test) - dt.date.fromisoformat(t_val)).days,
                  "test_days": (dt.date.fromisoformat(DATA_END) - dt.date.fromisoformat(t_test)).days + 1,
                  "train_positives_raw": train.count(), "train_positives_core": core.count(),
                  "core_users": cu.count(), "core_items": ci.count(), "kcore_rounds": rounds}
            st["val"] = _window_stats(pos.filter((F.col("date") >= t_val) & (F.col("date") < t_test)), cu, ci,
                                      games, t_val)
            st["test"] = _window_stats(pos.filter(F.col("date") >= t_test), cu, ci, games, t_test)
            core.unpersist()
            rep["candidates"].append(st)
            pm.update(core_users=st["core_users"], val_users=st["val"]["eval_users"],
                      test_users=st["test"]["eval_users"])
            LOG.info("candidate %s", json.dumps(st))

    (out_dir / "eda_time_split.json").write_text(json.dumps(rep, indent=2, default=str))
    return rep
