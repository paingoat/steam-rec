"""Bronze -> Silver: typed, cleaned, deduplicated Parquet + DQ report. Non-full scales sample whole users."""

from __future__ import annotations

import json

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from steam_rec.common.logging import phase
from steam_rec.pipelines.bronze_reader import bronze_manifest, read_bronze
from steam_rec.pipelines.dq import DQ
from steam_rec.pipelines.runner import Ctx
from steam_rec.storage import paths

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


LIST_COLS = ("genres", "categories", "developers", "publishers")


def enrich_meta(meta: DataFrame, hf: DataFrame | None = None, ss: DataFrame | None = None) -> DataFrame:
    """meta[app_id, description, tags] + HF (short_description, genres, categories, developers, publishers)
    + SteamSpy (tags). Precedence: Kaggle v28 first, then the enrichment source. Adds tags_src / desc_src."""
    if ss is None:
        out = meta.withColumn("_ss_tags", F.lit(None).cast("array<string>"))
    else:
        out = meta.join(ss.select("app_id", F.col("tags").alias("_ss_tags")), "app_id", "left")
    if hf is None:
        out = out.withColumn("_hf_desc", F.lit(None).cast("string"))
        for c in LIST_COLS:
            out = out.withColumn(c, F.lit(None).cast("array<string>"))
    else:
        out = out.join(hf.select("app_id", F.col("short_description").alias("_hf_desc"), *LIST_COLS), "app_id", "left")
    empty = F.array().cast("array<string>")  # built lazily: needs an active SparkSession
    v28_tags = F.coalesce(F.size("tags"), F.lit(0)) > 0
    ss_tags = F.coalesce(F.size("_ss_tags"), F.lit(0)) > 0
    hf_desc = F.when(F.length(F.trim("_hf_desc")) > 0, F.trim("_hf_desc"))
    out = (out.withColumn("tags_src", F.when(v28_tags, "v28").when(ss_tags, "steamspy").otherwise("none"))
           .withColumn("tags", F.when(v28_tags, F.col("tags")).when(ss_tags, F.col("_ss_tags")).otherwise(empty))
           .withColumn("desc_src", F.when(F.col("description").isNotNull(), "v28")
                       .when(hf_desc.isNotNull(), "hf").otherwise("none"))
           .withColumn("description", F.coalesce("description", hf_desc)))
    for c in LIST_COLS:
        out = out.withColumn(c, F.coalesce(c, empty))
    return out.drop("_ss_tags", "_hf_desc")


def read_game_meta(ctx: Ctx) -> tuple[DataFrame | None, DataFrame | None]:
    """Latest enrichment snapshots (None when `steam-rec ingest-meta` was never run -> v1 behaviour)."""
    if not ctx.store.exists(paths.bronze_meta_latest()):
        return None, None
    latest = json.loads(ctx.store.get_text(paths.bronze_meta_latest()))
    rd = lambda src: ctx.spark.read.parquet(ctx.uri(f"{paths.bronze_meta_prefix(src, latest[src])}/raw/{src}.parquet")) \
        if src in latest else None
    ss = rd("steamspy")
    return rd("hf"), (ss.filter("status = 'ok'") if ss is not None else None)


def orphan_keys(df: DataFrame, ref: DataFrame, key: str) -> int:
    """Distinct `key` values of df that do not exist in ref (foreign-key violations)."""
    return df.select(key).distinct().join(ref.select(key), key, "left_anti").count()


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
        hf, ss = read_game_meta(ctx)
        meta = enrich_meta(meta, hf, ss)
        catalog = games.join(meta, "app_id", "left")
        dq.check("game_catalog.rows_eq_games", catalog.count(), catalog.count() == n_games)
        dq.check("games_metadata.empty_description", meta.filter("description IS NULL").count(), True, "warn")
        ctx.write(catalog.coalesce(1), ctx.silver("game_catalog"))
        catalog = ctx.read(ctx.silver("game_catalog"))
        cov = catalog.agg(F.avg((F.size("tags") > 0).cast("double")).alias("tags"),
                          F.avg(F.col("description").isNotNull().cast("double")).alias("desc")).first()
        dq.check("game_catalog.games_with_tags_pct", round(cov["tags"] * 100, 2), True, "warn")
        dq.check("game_catalog.games_with_desc_pct", round(cov["desc"] * 100, 2), True, "warn")
        src = {f"{r['tags_src']}/{r['desc_src']}": r["count"]
               for r in catalog.groupBy("tags_src", "desc_src").count().collect()}
        dq.check("game_catalog.sources", src, True, "warn")
        pm.update(games=n_games, enriched=hf is not None or ss is not None)

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
        orphan = orphan_keys(recs, games, "app_id")
        dq.check("recs.fk_app_id", orphan, orphan == 0)
        orphan_u = orphan_keys(recs, raw["users"], "user_id")  # against the full Bronze users table
        dq.check("recs.fk_user_id", orphan_u, orphan_u == 0)
        tagged = catalog.filter(F.size("tags") > 0).select("app_id")
        pos_tagged = recs.filter("is_recommended").join(F.broadcast(tagged), "app_id", "left_semi").count()
        n_pos = recs.filter("is_recommended").count()
        dq.check("recs.positives_on_tagged_games_pct", round(100 * pos_tagged / max(1, n_pos), 2), True, "warn")
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
