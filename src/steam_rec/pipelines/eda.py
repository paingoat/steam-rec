"""M3 EDA on the full Bronze snapshot. Only aggregates reach the driver (no collect of big tables)."""

from __future__ import annotations

import json
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from steam_rec.common.config import REPO_ROOT, Config
from steam_rec.common.logging import LOG, phase
from steam_rec.common.schemas import RAW_HEADERS
from steam_rec.common.spark import get_spark
from steam_rec.pipelines.bronze_reader import bronze_manifest, read_bronze
from steam_rec.storage import paths
from steam_rec.storage.store import Store

QS = [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999]
KCORE_GRID = [(1, 1), (3, 5), (5, 10), (5, 20), (10, 20)]


def _quantiles(df: DataFrame, col: str) -> dict:
    """Exact percentiles (approxQuantile's rank error misreports heavy tails) + max."""
    qs = ", ".join(str(q) for q in QS)
    row = df.agg(F.expr(f"percentile({col}, array({qs}))").alias("q"), F.max(col).alias("max")).first()
    out = {f"p{q * 100:g}": round(float(v), 3) for q, v in zip(QS, row["q"], strict=True)}
    out["max"] = row["max"]
    return out


def _thresholds(df: DataFrame, col: str, ts=(1, 2, 3, 5, 10, 20, 50)) -> dict:
    row = df.agg(*[F.sum((F.col(col) >= t).cast("long")).alias(f">={t}") for t in ts]).first()
    return row.asDict()


def _nulls(df: DataFrame) -> dict:
    return df.agg(*[F.sum(F.col(c).isNull().cast("long")).alias(c) for c in df.columns]).first().asDict()


def kcore(pos: DataFrame, min_u: int, min_i: int, rounds: int = 8) -> tuple[DataFrame, int]:
    """Iterative k-core. Each round is checkpointed to disk so the plan/lineage does not grow (OOM otherwise)."""
    cur, n_cur = pos, pos.count()
    for r in range(1, rounds + 1):
        u = cur.groupBy("user_id").count().filter(F.col("count") >= min_u).select("user_id")
        i = cur.groupBy("app_id").count().filter(F.col("count") >= min_i).select("app_id")
        nxt = cur.join(F.broadcast(i), "app_id").join(u, "user_id").checkpoint(eager=True)
        n_nxt = nxt.count()
        cur = nxt
        if n_nxt == n_cur:
            return cur, r
        n_cur = n_nxt
    LOG.warning("k-core (%s,%s) not converged after %s rounds", min_u, min_i, rounds)
    return cur, -rounds


def run_eda(cfg: Config, store: Store, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or REPO_ROOT / "reports" / "eda"
    out_dir.mkdir(parents=True, exist_ok=True)
    spark = get_spark(cfg, "eda")
    man = bronze_manifest(cfg, store)
    dfs = read_bronze(spark, cfg, store, man)
    rep: dict = {"bronze_ingest_run_id": man["ingest_run_id"], "dataset_version": cfg.dataset.version}

    with phase("eda.headers"):
        hdr = {}
        for f, expected in RAW_HEADERS.items():
            got = spark.read.text(store.uri(paths.bronze_raw(cfg.dataset.version, man["ingest_run_id"], f))).first()[0]
            hdr[f] = {"matches": got.split(",") == expected, "header": got}
        rep["headers"] = hdr

    g, u, m = dfs["games"], dfs["users"], dfs["games_metadata"]
    r = dfs["recommendations"].withColumn("date", F.to_date("date"))
    r.persist(StorageLevel.MEMORY_AND_DISK)

    with phase("eda.basic") as mt:
        rep["rows"] = {k: v.count() for k, v in {"games": g, "users": u, "games_metadata": m, "recommendations": r}.items()}
        rep["nulls"] = {"games": _nulls(g), "users": _nulls(u), "recommendations": _nulls(r)}
        rep["games_metadata_schema"] = m.schema.simpleString()
        mt.update(rep["rows"])

    with phase("eda.recommendations"):
        agg = r.agg(
            F.countDistinct("review_id").alias("distinct_review_id"),
            F.countDistinct("user_id").alias("distinct_users"),
            F.countDistinct("app_id").alias("distinct_apps"),
            F.avg(F.col("is_recommended").cast("double")).alias("positive_rate"),
            F.sum((F.col("hours") == 0).cast("long")).alias("hours_zero"),
            F.sum((F.col("hours") < 0).cast("long")).alias("hours_negative"),
            F.max("hours").alias("hours_max"),
            F.min("date").cast("string").alias("date_min"),
            F.max("date").cast("string").alias("date_max"),
        ).first().asDict()
        agg["dup_user_app_pairs"] = r.groupBy("user_id", "app_id").count().filter("count > 1").count()
        rep["recommendations"] = agg
        rep["hours_quantiles"] = _quantiles(r, "hours")
        rep["hours_quantiles_positive"] = _quantiles(r.filter("is_recommended"), "hours")
        rep["hours_quantiles_negative"] = _quantiles(r.filter("NOT is_recommended"), "hours")
        rep["by_year"] = {str(x["y"]): [x["n"], round(x["pos"], 4)] for x in
                          r.groupBy(F.year("date").alias("y")).agg(F.count("*").alias("n"),
                          F.avg(F.col("is_recommended").cast("double")).alias("pos")).orderBy("y").collect()}

    with phase("eda.degrees"):
        pu = r.groupBy("user_id").agg(F.count("*").alias("n_all"),
                                      F.sum(F.col("is_recommended").cast("int")).alias("n_pos"))
        pi = r.groupBy("app_id").agg(F.count("*").alias("n_all"),
                                     F.sum(F.col("is_recommended").cast("int")).alias("n_pos"))
        pu.persist(StorageLevel.MEMORY_AND_DISK)
        rep["user_degree_all"] = {"quantiles": _quantiles(pu, "n_all"), "users_with": _thresholds(pu, "n_all")}
        rep["user_degree_pos"] = {"quantiles": _quantiles(pu, "n_pos"), "users_with": _thresholds(pu, "n_pos")}
        rep["item_degree_all"] = {"quantiles": _quantiles(pi, "n_all"), "items_with": _thresholds(pi, "n_all")}
        rep["item_degree_pos"] = {"quantiles": _quantiles(pi, "n_pos"), "items_with": _thresholds(pi, "n_pos")}
        # log2 buckets for charts
        rep["chart_user_degree_hist"] = {int(x["b"]): x["n"] for x in pu.groupBy(
            F.floor(F.log2("n_all")).alias("b")).count().withColumnRenamed("count", "n").collect()}
        rep["chart_hours_hist"] = {int(x["b"]): x["n"] for x in r.groupBy(
            F.floor(F.log2(F.col("hours") + 1)).alias("b")).count().withColumnRenamed("count", "n").collect()}

    with phase("eda.consistency"):
        games_ids = g.select("app_id").distinct()
        rep["fk"] = {
            "rec_apps_not_in_games": r.select("app_id").distinct().join(games_ids, "app_id", "left_anti").count(),
            "rec_users_not_in_users": pu.select("user_id").join(u.select("user_id"), "user_id", "left_anti").count(),
            "users_without_recs": u.select("user_id").join(pu.select("user_id"), "user_id", "left_anti").count(),
            "games_without_metadata": games_ids.join(m.select("app_id"), "app_id", "left_anti").count(),
            "users_reviews_field_mismatch": u.join(pu, "user_id").filter(F.col("reviews") != F.col("n_all")).count(),
        }
        mm = m.select("app_id", F.trim("description").alias("d"), F.size("tags").alias("nt"))
        rep["metadata"] = mm.agg(
            F.sum((F.col("d").isNull() | (F.col("d") == "")).cast("long")).alias("empty_description"),
            F.sum((F.col("nt") <= 0).cast("long")).alias("no_tags"),
            F.avg("nt").alias("avg_tags"),
            F.avg(F.length("d")).alias("avg_desc_chars"),
        ).first().asDict()
        rep["metadata"]["distinct_tags"] = m.select(F.explode("tags")).distinct().count()

    with phase("eda.split_feasibility"):
        pos = r.filter("is_recommended").select("user_id", "app_id", "date", "review_id")
        w = Window.partitionBy("user_id").orderBy(F.col("date").desc(), F.col("review_id").desc())
        last2 = pos.withColumn("rk", F.row_number().over(w)).filter("rk <= 2")
        ties = last2.groupBy("user_id").agg(F.countDistinct("date").alias("nd"), F.count("*").alias("n")) \
            .filter("n = 2")
        rep["split"] = {
            "users_ge3_pos": pu.filter("n_pos >= 3").count(),
            "users_last2_pos_same_date": ties.filter("nd = 1").count(),
            "users_last2_pos_total": ties.count(),
        }

    with phase("eda.kcore"):
        posp = r.filter("is_recommended").select("user_id", "app_id").persist(StorageLevel.DISK_ONLY)
        n_users_total, n_items_total = rep["recommendations"]["distinct_users"], rep["recommendations"]["distinct_apps"]
        rep["kcore_positive"] = []
        for mu, mi in KCORE_GRID:
            core, rounds = kcore(posp, mu, mi)
            st = core.agg(F.count("*").alias("n"), F.countDistinct("user_id").alias("users"),
                          F.countDistinct("app_id").alias("items")).first().asDict()
            st.update(min_user=mu, min_item=mi, rounds=rounds,
                      density=st["n"] / max(1, st["users"] * st["items"]),
                      user_retention=st["users"] / n_users_total, item_retention=st["items"] / n_items_total,
                      als_factor_gb_rank64=round((st["users"] + st["items"]) * 64 * 4 / 1e9, 2))
            rep["kcore_positive"].append(st)
            LOG.info("kcore %s", st)

    (out_dir / "eda_summary.json").write_text(json.dumps(rep, indent=2, default=str))
    spark.stop()
    import shutil

    for d in cfg.resolve_path(cfg.spark.checkpoint_dir).glob("*"):
        shutil.rmtree(d, ignore_errors=True)  # k-core checkpoints are scratch (~20 GB on full data)
    return rep
