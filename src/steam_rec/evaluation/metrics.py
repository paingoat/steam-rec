"""Ranking metrics with a SET of held-out targets per user (global temporal split: every positive of the user inside
the evaluation window is relevant). Pure-Python reference + Spark aggregation (same formulas).

  Recall@K = |top-K ∩ rel| / min(K, |rel|)        (normalised, so a perfect ranker scores 1 even when |rel| > K)
  NDCG@K   = Σ_{i≤K, rec_i∈rel} 1/log2(i+1)  /  Σ_{i≤min(K,|rel|)} 1/log2(i+1)
Both are averaged over evaluation users."""

from __future__ import annotations

import math

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def recall_at_k(recs: list[int], targets: list[int], k: int) -> float:
    rel = set(targets)
    return len(set(recs[:k]) & rel) / min(k, len(rel)) if rel else 0.0


def ndcg_at_k(recs: list[int], targets: list[int], k: int) -> float:
    rel = set(targets)
    if not rel:
        return 0.0
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(recs[:k]) if r in rel)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(rel))))
    return dcg / idcg


def spark_metrics(topk: DataFrame, target_col: str, ks: list[int], n_items: int) -> dict:
    """topk: user_idx, items array<int> (ordered), <target_col> array<int> (non-empty)."""
    t = target_col
    aggs = [F.count("*").alias("users"), F.avg(F.size(t)).alias("targets_per_user")]
    for k in ks:
        hits = F.size(F.array_intersect(F.slice("items", 1, k), F.col(t)))
        dcg = F.expr(f"IF(size(items) = 0, 0D, aggregate(sequence(1, least(size(items), {k})), 0D, "
                     f"(acc, i) -> acc + IF(array_contains({t}, element_at(items, i)), 1D / log2(i + 1), 0D)))")
        idcg = F.expr(f"aggregate(sequence(1, least(size({t}), {k})), 0D, (acc, i) -> acc + 1D / log2(i + 1))")
        aggs += [
            F.avg(hits / F.least(F.size(t), F.lit(k))).alias(f"recall@{k}"),
            F.avg(dcg / idcg).alias(f"ndcg@{k}"),
            F.avg((F.size("items") >= k).cast("double")).alias(f"eligible_user_coverage@{k}"),
        ]
    out = topk.agg(*aggs).first().asDict()
    for k in ks:
        n_distinct = topk.select(F.explode(F.slice("items", 1, k)).alias("i")).distinct().count()
        out[f"catalog_coverage@{k}"] = n_distinct / max(1, n_items)
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in out.items()}
