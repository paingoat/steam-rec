from __future__ import annotations

import numpy as np
from pyspark.sql import functions as F

from steam_rec.pipelines.runner import Ctx


def fit_popularity(ctx: Ctx, n_items: int) -> np.ndarray:
    """Train-positive count per item_idx (train split only -> no leakage)."""
    rows = (ctx.read(ctx.gold("interactions")).filter("split = 'train'")
            .groupBy("item_idx").agg(F.count("*").alias("n")).collect())
    pop = np.zeros(n_items, np.float32)
    for r in rows:
        pop[r["item_idx"]] = r["n"]
    return pop
