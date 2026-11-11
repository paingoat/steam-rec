"""Ranking metrics with one held-out target per user. Pure-Python reference + Spark aggregation (same formulas)."""

from __future__ import annotations

import math

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def hit_rank(recs: list[int], target: int) -> int:
    """1-based rank of target in recs, 0 if absent."""
    return recs.index(target) + 1 if target in recs else 0


def recall_at_k(recs: list[int], target: int, k: int) -> float:
    r = hit_rank(recs[:k], target)
    return 1.0 if r else 0.0


def ndcg_at_k(recs: list[int], target: int, k: int) -> float:
    r = hit_rank(recs[:k], target)
    return 1.0 / math.log2(r + 1) if r else 0.0  # ideal DCG = 1 for a single relevant item


def spark_metrics(topk: DataFrame, target_col: str, ks: list[int], n_items: int) -> dict:
    """topk: user_idx, items array<int> (ordered), <target_col> int."""
    df = topk.withColumn("_pos", F.array_position("items", F.col(target_col)).cast("int"))
    aggs = [F.count("*").alias("users")]
    for k in ks:
        hit = (F.col("_pos") >= 1) & (F.col("_pos") <= k)
        aggs += [
            F.avg(hit.cast("double")).alias(f"recall@{k}"),
            F.avg(F.when(hit, 1.0 / F.log2(F.col("_pos") + 1)).otherwise(0.0)).alias(f"ndcg@{k}"),
            F.avg((F.size("items") >= k).cast("double")).alias(f"eligible_user_coverage@{k}"),
        ]
    out = df.agg(*aggs).first().asDict()
    for k in ks:
        n_distinct = topk.select(F.explode(F.slice("items", 1, k)).alias("i")).distinct().count()
        out[f"catalog_coverage@{k}"] = n_distinct / max(1, n_items)
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in out.items()}
