"""Silver -> Gold: global temporal split -> k-core on train -> int id maps, masking history, eval targets, demo users."""

from __future__ import annotations

from pyspark.sql import Window
from pyspark.sql import functions as F

from steam_rec.common.logging import phase
from steam_rec.features.cf_interactions import confidence, kcore
from steam_rec.features.splits import global_time_split
from steam_rec.pipelines.runner import Ctx

HASH_BUCKETS = 1_000_000


def _index(df, col: str, idx_col: str):
    """Contiguous int ids (ALS needs int). Single-partition window is fine for ≤ a few million keys."""
    return df.select(col).distinct().withColumn(idx_col, (F.row_number().over(Window.orderBy(col)) - 1).cast("int"))


def run_gold(ctx: Ctx) -> dict:
    cfg, g = ctx.cfg, ctx.cfg.gold
    recs = ctx.read(ctx.silver("recommendations")).drop("year")
    m: dict = {}

    t_val, t_test = cfg.split.t_val, cfg.split.t_test
    if not (t_val and t_test):
        raise ValueError("split.t_val / split.t_test must be set (see reports/eda_time_split.md)")
    m["split_dates"] = {"t_val": t_val, "t_test": t_test}

    with phase("gold.split_kcore") as pm:
        # 1) global time split  2) k-core on TRAIN only  3) val/test keep users AND items of the train core
        pos = global_time_split(recs.filter("is_recommended"), t_val, t_test)
        train = pos.filter("split = 'train'")
        core, rounds = kcore(train.select("user_id", "app_id"), g.min_user_pos, g.min_item_pos, g.kcore_max_rounds)
        train_core = train.join(core, ["user_id", "app_id"], "left_semi")
        users = _index(train_core, "user_id", "user_idx").checkpoint(eager=True)
        items = _index(train_core, "app_id", "item_idx").checkpoint(eager=True)
        win = pos.filter("split != 'train'")
        win_users = win.join(users.select("user_id"), "user_id", "left_semi")
        warm = win_users.join(F.broadcast(items.select("app_id")), "app_id", "left_semi")
        win_stats = {f"{s_}_{k}": v for s_ in ("val", "test") for k, v in (
            ("positives", win.filter(F.col("split") == s_).count()),
            ("positives_core_users", win_users.filter(F.col("split") == s_).count()),
            ("warm_targets", warm.filter(F.col("split") == s_).count()))}
        pm.update(train_pos=train.count(), train_core=train_core.count(), rounds=rounds, **win_stats)
        m["kcore"] = dict(pm)

    with phase("gold.ids") as pm:
        inter = (train_core.unionByName(warm).withColumn("confidence", confidence())
                 .join(F.broadcast(items), "app_id").join(users, "user_id")
                 .select("user_idx", "item_idx", "user_id", "app_id", "date", "review_id", "hours",
                         "confidence", "split"))
        ctx.write(users, ctx.gold("id_map_users"))
        ctx.write(items.coalesce(1), ctx.gold("id_map_items"))
        ctx.write(inter, ctx.gold("interactions"))
        inter = ctx.read(ctx.gold("interactions"))
        counts = {r["split"]: r["count"] for r in inter.groupBy("split").count().collect()}
        n_users, n_items = users.count(), items.count()
        pm.update(users=n_users, items=n_items, **{f"n_{k}": v for k, v in counts.items()},
                  density_train=counts.get("train", 0) / max(1, n_users * n_items))
        m["split"] = dict(pm)

    with phase("gold.history") as pm:
        # Everything the user did on core items (positives + negatives if masked). Used only for candidate masking:
        # when scoring a window starting at cutoff_date the mask is the history with date < cutoff_date.
        hist = recs if g.negatives == "mask" else recs.filter("is_recommended")
        hist = (hist.join(F.broadcast(items), "app_id").join(users, "user_id")
                .select("user_idx", "item_idx", "date", "review_id", "is_recommended"))
        ctx.write(hist, ctx.gold("history"))
        pm.update(rows=ctx.read(ctx.gold("history")).count())
        m["history"] = dict(pm)

    with phase("gold.eval_targets") as pm:
        # one row per (user, split): every warm positive inside the window is a relevant target
        h = F.pmod(F.xxhash64("user_idx", F.lit(cfg.scale.sample_seed)), F.lit(HASH_BUCKETS))
        cutoff = F.when(F.col("split") == "val", F.lit(t_val)).otherwise(F.lit(t_test)).cast("date")
        tgt = (inter.filter("split IN ('val','test')").groupBy("user_idx", "split")
               .agg(F.sort_array(F.collect_set("item_idx")).alias("items"))
               .withColumn("cutoff_date", cutoff).withColumn("_h", h))
        cands = {r["split"]: r["count"] for r in tgt.groupBy("split").count().collect()}
        ranked = None
        for s_ in ("val", "test"):  # deterministic sample, same users for every model
            part = tgt.filter(F.col("split") == s_).orderBy("_h", "user_idx").limit(cfg.eval.max_eval_users)
            ranked = part if ranked is None else ranked.unionByName(part)
        ctx.write(ranked.drop("_h").coalesce(4), ctx.gold("eval_targets"))
        ev = ctx.read(ctx.gold("eval_targets"))
        n_eval = {r["split"]: r["count"] for r in ev.groupBy("split").count().collect()}
        demo = (users.join(ev.select("user_idx"), "user_idx", "left_anti")
                .withColumn("_h", F.pmod(F.xxhash64("user_idx", F.lit(cfg.scale.sample_seed)), F.lit(HASH_BUCKETS)))
                .orderBy("_h").limit(g.demo_users).select("user_idx"))
        ctx.write(demo.coalesce(1), ctx.gold("demo_users"))
        pm.update(**{f"{k}_candidates": v for k, v in cands.items()}, **{f"{k}_eval_users": v for k, v in n_eval.items()})
        m["eval"] = dict(pm)
    return m
