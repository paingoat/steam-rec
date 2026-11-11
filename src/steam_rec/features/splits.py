"""Per-user temporal leave-last-out split on positives."""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def leave_last_out(pos: DataFrame, min_pos_for_eval: int = 3, user_col: str = "user_id") -> DataFrame:
    """Adds `split`: last positive (by date, then review_id) -> test, second-to-last -> val, rest -> train.
    Users with < min_pos_for_eval positives keep everything in train."""
    w = Window.partitionBy(user_col).orderBy(F.col("date").desc(), F.col("review_id").desc())
    wn = Window.partitionBy(user_col)
    return (
        pos.withColumn("_rk", F.row_number().over(w)).withColumn("_n", F.count("*").over(wn))
        .withColumn("split", F.when((F.col("_n") >= min_pos_for_eval) & (F.col("_rk") == 1), "test")
                    .when((F.col("_n") >= min_pos_for_eval) & (F.col("_rk") == 2), "val").otherwise("train"))
        .drop("_rk", "_n")
    )
