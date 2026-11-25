"""Global temporal split (production-style): one cut-off for every user, so no model ever sees the future of anyone.

  train = date <  t_val
  val   = t_val <= date < t_test
  test  = date >= t_test
(The per-user leave-last-out split of v1 was removed: it leaked other users' future interactions into training.)"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def global_time_split(df: DataFrame, t_val: str, t_test: str, date_col: str = "date") -> DataFrame:
    if not t_val < t_test:
        raise ValueError(f"need t_val < t_test, got {t_val} / {t_test}")
    d = F.col(date_col)
    return df.withColumn("split", F.when(d < F.lit(t_val).cast("date"), "train")
                         .when(d < F.lit(t_test).cast("date"), "val").otherwise("test"))
