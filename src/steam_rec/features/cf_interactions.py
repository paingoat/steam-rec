from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from steam_rec.common.logging import LOG


def confidence(hours_col: str = "hours") -> Column:
    """Implicit-feedback confidence weight; ALS alpha scales it further. Source caps hours at 1000."""
    return (F.lit(1.0) + F.log1p(F.greatest(F.col(hours_col), F.lit(0.0)))).cast("float")


def kcore(pos: DataFrame, min_u: int, min_i: int, rounds: int = 8,
          user_col: str = "user_id", item_col: str = "app_id") -> tuple[DataFrame, int]:
    """Iterative k-core on (user,item) pairs. Each round is checkpointed so the plan/lineage does not grow
    (an un-checkpointed loop OOMs the driver on the full data). Returns (core, rounds; negative = not converged)."""
    cur, n_cur = pos, pos.count()
    for r in range(1, rounds + 1):
        u = cur.groupBy(user_col).count().filter(F.col("count") >= min_u).select(user_col)
        i = cur.groupBy(item_col).count().filter(F.col("count") >= min_i).select(item_col)
        nxt = cur.join(F.broadcast(i), item_col).join(u, user_col).checkpoint(eager=True)
        n_nxt = nxt.count()
        cur = nxt
        if n_nxt == n_cur:
            return cur, r
        n_cur = n_nxt
    LOG.warning("k-core (%s,%s) not converged after %s rounds", min_u, min_i, rounds)
    return cur, -rounds
