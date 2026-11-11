"""Exact top-K scoring without user×item crossJoin.

Per-user inputs (mask, train history, optional ALS factors) are built in Spark; scores are computed in
`mapInPandas` batches against a small broadcast item-side state (popularity vector, ALS item factors, or
CB item-kNN sparse matrix). Only the item side is broadcast (≈ tens of MB for ~33k items)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, FloatType, IntegerType, StructField, StructType

from steam_rec.pipelines.runner import Ctx

OUT_SCHEMA = StructType([
    StructField("user_idx", IntegerType()),
    StructField("items", ArrayType(IntegerType())),
    StructField("scores", ArrayType(FloatType())),
])


def user_inputs(ctx: Ctx, users: DataFrame, cutoff: str) -> DataFrame:
    """users: user_idx (+ <cutoff>_date, <cutoff>_review_id when cutoff in {val,test}).
    mask = items interacted strictly before the target (or all history when cutoff='all').
    hist = train positives with confidence (model input; identical for every model)."""
    hist = ctx.read(ctx.gold("history"))
    if cutoff in ("val", "test"):
        d, r = F.col(f"{cutoff}_date"), F.col(f"{cutoff}_review_id")
        before = (F.col("date") < d) | ((F.col("date") == d) & (F.col("review_id") < r))
        masked = hist.join(users.select("user_idx", d, r), "user_idx").filter(before)
    else:
        masked = hist.join(users.select("user_idx"), "user_idx")
    mask = masked.groupBy("user_idx").agg(F.collect_set("item_idx").alias("mask"))
    train = (ctx.read(ctx.gold("interactions")).filter("split = 'train'")
             .join(users.select("user_idx"), "user_idx")
             .groupBy("user_idx").agg(F.collect_list("item_idx").alias("hist_items"),
                                      F.collect_list("confidence").alias("hist_w")))
    return users.select("user_idx").join(mask, "user_idx", "left").join(train, "user_idx", "left")


def _topk_rows(scores: np.ndarray, masks, k: int):
    for row, m in zip(scores, masks, strict=True):
        if m is not None and len(m):
            row[np.asarray(m, dtype=np.int64)] = -np.inf
        kk = min(k, int(np.isfinite(row).sum()))
        if kk == 0:
            yield [], []
            continue
        top = np.argpartition(-row, kk - 1)[:kk]
        top = top[np.argsort(-row[top], kind="stable")]
        yield top.astype(np.int32).tolist(), row[top].astype(np.float32).tolist()


def topk(inputs: DataFrame, kind: str, state, k: int, batch: int = 256) -> DataFrame:
    """kind: 'pop' (state=np.ndarray[n_items]), 'als' (state=item factors [n_items, r]; inputs need `features`),
    'cb' (state=scipy CSR item-item sim)."""
    sc = inputs.sparkSession.sparkContext
    bc = sc.broadcast(state)

    def score_batch(pdf: pd.DataFrame) -> np.ndarray:
        st = bc.value
        n = len(pdf)
        if kind == "pop":
            return np.tile(st.astype(np.float32), (n, 1))
        if kind == "als":
            feats = [f if f is not None else np.zeros(st.shape[1], np.float32) for f in pdf["features"]]
            return np.asarray(np.stack(feats), np.float32) @ st.T
        if kind == "cb":
            from scipy.sparse import csr_matrix

            rows, cols, vals = [], [], []
            for i, (its, ws) in enumerate(zip(pdf["hist_items"], pdf["hist_w"], strict=True)):
                if its is not None:
                    rows += [i] * len(its)
                    cols += list(its)
                    vals += list(ws)
            h = csr_matrix((np.asarray(vals, np.float32), (rows, cols)), shape=(n, st.shape[0]))
            return np.asarray((h @ st).todense(), np.float32)
        raise ValueError(kind)

    def fn(it):
        for pdf in it:
            for s in range(0, len(pdf), batch):
                part = pdf.iloc[s:s + batch]
                sc_ = score_batch(part)
                if kind == "cb":  # zero-score items carry no signal -> not recommendable
                    sc_[sc_ <= 0] = -np.inf
                items, scores = zip(*_topk_rows(sc_, part["mask"], k), strict=True) if len(part) else ((), ())
                yield pd.DataFrame({"user_idx": part["user_idx"].astype("int32").values,
                                    "items": list(items), "scores": list(scores)})

    cols = ["user_idx", "mask", "hist_items", "hist_w"] + (["features"] if kind == "als" else [])
    return inputs.select(*cols).mapInPandas(fn, OUT_SCHEMA)
