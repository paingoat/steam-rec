"""Bronze -> Silver: typed, cleaned, deduplicated Parquet + DQ report. Non-full scales sample whole users."""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from steam_rec.common.logging import phase
from steam_rec.pipelines.bronze_reader import bronze_manifest, read_bronze
from steam_rec.pipelines.dq import DQ
from steam_rec.pipelines.runner import Ctx

HASH_BUCKETS = 1_000_000


def sample_users(df: DataFrame, fraction: float, seed: int) -> DataFrame:
    """Deterministic user-level sample: keeps complete histories (row sampling would destroy per-user data)."""
    if fraction >= 1:
        return df
    h = F.pmod(F.xxhash64(F.col("user_id"), F.lit(seed)), F.lit(HASH_BUCKETS))
    return df.filter(h < F.lit(int(fraction * HASH_BUCKETS)))


def dedup_user_app(recs: DataFrame) -> DataFrame:
    w = Window.partitionBy("user_id", "app_id").orderBy(F.col("date").desc(), F.col("review_id").desc())
    return recs.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


def run_silver(ctx: Ctx) -> dict:
    cfg, spark = ctx.cfg, ctx.spark
    man = bronze_manifest(cfg, ctx.store)
    raw = read_bronze(spark, cfg, ctx.store, man)
    dq, m = DQ(), {"bronze_ingest_run_id": man["ingest_run_id"]}

    with phase("silver.games") as pm:
        games = raw["games"].withColumn("title", F.trim("title")).withColumn("date_release", F.to_date("date_release"))
        meta = raw["games_metadata"].select(
            F.col("app_id").cast("int").alias("app_id"),
            F.when(F.length(F.trim("description")) > 0, F.trim("description")).alias("description"),
            F.coalesce(F.col("tags"), F.array().cast("array<string>")).alias("tags"),
        )
        n_games = games.count()
        dq.check("games.pk_unique", n_games - games.select("app_id").distinct().count(), n_games ==
                 games.select("app_id").distinct().count())
        dq.check("games_metadata.fk_games", meta.join(games, "app_id", "left_anti").count(),
                 meta.join(games, "app_id", "left_anti").count() == 0)
        catalog = games.join(meta, "app_id", "left")
        dq.check("game_catalog.rows_eq_games", catalog.count(), catalog.count() == n_games)
        dq.check("games_metadata.empty_description", meta.filter("description IS NULL").count(), True, "warn")
        ctx.write(catalog.coalesce(1), ctx.silver("game_catalog"))
        pm.update(games=n_games)

    with phase("silver.recommendations") as pm:
        total = raw["recommendations"].count()
        frac = 1.0 if cfg.scale.max_recommendations is None else min(1.0, cfg.scale.max_recommendations / total)
        recs = sample_users(raw["recommendations"], frac, cfg.scale.sample_seed).withColumn("date", F.to_date("date"))
        n_in = recs.count()
        dq.check("recs.null_keys", recs.filter("user_id IS NULL OR app_id IS NULL OR review_id IS NULL").count(),
                 recs.filter("user_id IS NULL OR app_id IS NULL OR review_id IS NULL").count() == 0)
        dq.check("recs.null_date", recs.filter("date IS NULL").count(), recs.filter("date IS NULL").count() == 0)
        n_rid = recs.select("review_id").distinct().count()
        dq.check("recs.review_id_unique", n_in - n_rid, n_in == n_rid)
        neg = recs.filter("hours < 0").count()
        dq.check("recs.hours_non_negative", neg, neg == 0)
        dq.check("recs.hours_le_1000", recs.filter("hours > 1000").count(), True, "warn")
        orphan = recs.select("app_id").distinct().join(games.select("app_id"), "app_id", "left_anti").count()
        dq.check("recs.fk_app_id", orphan, orphan == 0)
        recs = dedup_user_app(recs)
        n_out = recs.count()
        dq.check("recs.dedup_removed", n_in - n_out, True, "warn")
        ctx.write(recs.withColumn("year", F.year("date")), ctx.silver("recommendations"), ["year"])
        pm.update(rows_bronze=total, sample_fraction=round(frac, 6), rows_in=n_in, rows_out=n_out)

    with phase("silver.users") as pm:
        users = raw["users"].join(recs.select("user_id").distinct(), "user_id", "left_semi") \
            if frac < 1 else raw["users"]
        n_u = users.count()
        dq.check("users.pk_unique", n_u - users.select("user_id").distinct().count(),
                 n_u == users.select("user_id").distinct().count())
        ctx.write(users, ctx.silver("users"))
        pm.update(users=n_u)

    m.update(games=n_games, recs_bronze=total, sample_fraction=frac, recs_in=n_in, recs_out=n_out, users=n_u)
    ctx.put_json(ctx.art("dq", "silver_dq.json"), dq.results)
    dq.raise_if_failed()
    return m
