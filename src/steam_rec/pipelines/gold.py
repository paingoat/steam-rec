"""Silver -> Gold: k-core, temporal split, int id maps, masking history, eval/demo users."""

from __future__ import annotations

from pyspark.sql import Window
from pyspark.sql import functions as F

from steam_rec.common.logging import phase
from steam_rec.features.cf_interactions import confidence, kcore
from steam_rec.features.splits import leave_last_out
from steam_rec.pipelines.runner import Ctx

HASH_BUCKETS = 1_000_000


def _index(df, col: str, idx_col: str):
    """Contiguous int ids (ALS needs int). Single-partition window is fine for ≤ a few million keys."""
    return df.select(col).distinct().withColumn(idx_col, (F.row_number().over(Window.orderBy(col)) - 1).cast("int"))


def run_gold(ctx: Ctx) -> dict:
    cfg, g = ctx.cfg, ctx.cfg.gold
    recs = ctx.read(ctx.silver("recommendations")).drop("year")
    m: dict = {}

    with phase("gold.kcore") as pm:
        pos = recs.filter("is_recommended")
        core, rounds = kcore(pos.select("user_id", "app_id"), g.min_user_pos, g.min_item_pos, g.kcore_max_rounds)
        pos_core = pos.join(core, ["user_id", "app_id"], "left_semi")
        pm.update(pos_in=pos.count(), pos_core=pos_core.count(), rounds=rounds)
        m["kcore"] = dict(pm)

    with phase("gold.split_and_ids") as pm:
        split = leave_last_out(pos_core, g.min_user_pos).withColumn("confidence", confidence())
        users = _index(split, "user_id", "user_idx")
        items = _index(split, "app_id", "item_idx")
        users = users.checkpoint(eager=True)
        items = items.checkpoint(eager=True)
        inter = (split.join(F.broadcast(items), "app_id").join(users, "user_id")
                 .select("user_idx", "item_idx", "user_id", "app_id", "date", "review_id", "hours",
                         "confidence", "split"))
        ctx.write(users, ctx.gold("id_map_users"))
        ctx.write(items.coalesce(1), ctx.gold("id_map_items"))
        ctx.write(inter, ctx.gold("interactions"))
        inter = ctx.read(ctx.gold("interactions"))
        counts = {r["split"]: r["count"] for r in inter.groupBy("split").count().collect()}
        n_users, n_items = users.count(), items.count()
        train_items = inter.filter("split = 'train'").select("item_idx").distinct().count()
        pm.update(users=n_users, items=n_items, train_items=train_items, **{f"n_{k}": v for k, v in counts.items()},
                  density_train=counts.get("train", 0) / max(1, n_users * n_items))
        m["split"] = dict(pm)

    with phase("gold.history") as pm:
        # Everything the user did on core items (positives + negatives if masked). Used only for candidate masking:
        # for a target at (date, review_id) the mask is the history strictly before it -> no future leakage.
        hist = recs if g.negatives == "mask" else recs.filter("is_recommended")
        hist = (hist.join(F.broadcast(items), "app_id").join(users, "user_id")
                .select("user_idx", "item_idx", "date", "review_id", "is_recommended"))
        ctx.write(hist, ctx.gold("history"))
        pm.update(rows=ctx.read(ctx.gold("history")).count())
        m["history"] = dict(pm)

    with phase("gold.eval_users") as pm:
        train_item_set = inter.filter("split = 'train'").select("item_idx").distinct()
        tgt = inter.filter("split IN ('val','test')")
        pivot = tgt.groupBy("user_idx").agg(
            *[F.max(F.when(F.col("split") == s, F.col(c))).alias(f"{s}_{c.replace('_idx', '')}")
              for s in ("val", "test") for c in ("item_idx", "date", "review_id")])
        pivot = pivot.filter("val_item IS NOT NULL AND test_item IS NOT NULL")
        n_candidates = pivot.count()
        # cold target items (no train interactions) are reported, not silently dropped from the denominator
        warm = pivot.join(train_item_set.withColumnRenamed("item_idx", "test_item"), "test_item", "left_semi") \
                    .join(train_item_set.withColumnRenamed("item_idx", "val_item"), "val_item", "left_semi")
        h = F.pmod(F.xxhash64("user_idx", F.lit(cfg.scale.sample_seed)), F.lit(HASH_BUCKETS))
        ranked = warm.withColumn("_h", h).orderBy("_h", "user_idx").limit(cfg.eval.max_eval_users).drop("_h")
        ctx.write(ranked.coalesce(4), ctx.gold("eval_targets"))
        n_eval = ctx.read(ctx.gold("eval_targets")).count()
        demo = (users.join(ranked.select("user_idx"), "user_idx", "left_anti")
                .withColumn("_h", h).orderBy("_h").limit(g.demo_users).select("user_idx"))
        ctx.write(demo.coalesce(1), ctx.gold("demo_users"))
        pm.update(eval_candidates=n_candidates, warm_candidates=warm.count(), eval_users=n_eval)
        m["eval"] = dict(pm)
    return m
