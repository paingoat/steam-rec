from __future__ import annotations

import numpy as np
from pyspark.ml.recommendation import ALS, ALSModel
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from steam_rec.pipelines.runner import Ctx


def fit_als(ctx: Ctx, params: dict) -> ALSModel:
    """Implicit ALS on train positives. rating = confidence (1+log1p(hours)); Spark uses c = 1 + alpha*rating."""
    train = ctx.read(ctx.gold("interactions")).filter("split = 'train'").select("user_idx", "item_idx", "confidence")
    als = ALS(userCol="user_idx", itemCol="item_idx", ratingCol="confidence", implicitPrefs=True,
              rank=int(params["rank"]), regParam=float(params["regParam"]), alpha=float(params["alpha"]),
              maxIter=int(params["maxIter"]), coldStartStrategy="drop", nonnegative=False,
              checkpointInterval=5, seed=ctx.cfg.scale.sample_seed,
              numUserBlocks=ctx.cfg.spark.shuffle_partitions, numItemBlocks=ctx.cfg.spark.shuffle_partitions)
    return als.fit(train)


def item_factors(model: ALSModel, n_items: int) -> np.ndarray:
    v = np.zeros((n_items, model.rank), np.float32)  # items without train data keep a zero vector (score 0)
    for r in model.itemFactors.collect():
        v[r["id"]] = r["features"]
    return v


def with_user_factors(inputs: DataFrame, model: ALSModel) -> DataFrame:
    uf = model.userFactors.select(F.col("id").alias("user_idx"), "features")
    return inputs.join(uf, "user_idx", "left")
