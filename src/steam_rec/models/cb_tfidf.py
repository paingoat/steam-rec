"""Content-based: TF-IDF(tags) ⊕ w·TF-IDF(description) -> L2 -> item-kNN cosine (top-N neighbors per item).

Spark computes vocabularies/IDF over the ~33k-item catalog (interaction-free, so no leakage); the item matrix
is small enough to collect, and kNN is computed block-wise so memory stays ≈ block × n_items floats."""

from __future__ import annotations

import numpy as np
from pyspark.ml.feature import IDF, CountVectorizer, RegexTokenizer, StopWordsRemover
from pyspark.sql import functions as F
from scipy import sparse

from steam_rec.pipelines.runner import Ctx


def l2_rows(m: sparse.csr_matrix) -> sparse.csr_matrix:
    norms = np.sqrt(np.asarray(m.multiply(m).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    return sparse.diags(1.0 / norms) @ m


def _to_csr(rows, n_items: int, dim: int) -> sparse.csr_matrix:
    r, c, v = [], [], []
    for item_idx, vec in rows:
        if vec is None:
            continue
        r += [item_idx] * len(vec.indices)
        c += vec.indices.tolist()
        v += vec.values.tolist()
    return sparse.csr_matrix((np.asarray(v, np.float32), (r, c)), shape=(n_items, dim))


def build_item_features(ctx: Ctx, n_items: int) -> dict:
    """Returns {'X_tag', 'X_desc' (L2-normalized CSR, rows = item_idx), 'tag_vocab', 'tag_idf'}."""
    p = ctx.cfg.model["cb"]
    items = ctx.read(ctx.gold("id_map_items"))
    cat = ctx.read(ctx.silver("game_catalog")).join(items, "app_id").select(
        "item_idx",
        F.transform("tags", lambda t: F.regexp_replace(F.lower(F.trim(t)), r"[^a-z0-9]+", "_")).alias("tag_tok"),
        F.coalesce("description", F.lit("")).alias("description"),
    )
    tag_cv = CountVectorizer(inputCol="tag_tok", outputCol="tag_tf", vocabSize=int(p["tag_vocab"]), binary=True)
    tag_model = tag_cv.fit(cat)
    df = tag_model.transform(cat)
    tag_idf = IDF(inputCol="tag_tf", outputCol="tag_vec").fit(df)
    df = tag_idf.transform(df)

    df = RegexTokenizer(inputCol="description", outputCol="d_tok", pattern=r"[^\p{L}\p{N}]+",
                        minTokenLength=3).transform(df)
    df = StopWordsRemover(inputCol="d_tok", outputCol="d_clean").transform(df)
    desc_model = CountVectorizer(inputCol="d_clean", outputCol="d_tf", vocabSize=int(p["desc_vocab"]),
                                 minDF=float(p["desc_min_df"])).fit(df)
    df = desc_model.transform(df)
    df = IDF(inputCol="d_tf", outputCol="d_vec").fit(df).transform(df)

    rows = df.select("item_idx", "tag_vec", "d_vec").collect()
    x_tag = l2_rows(_to_csr([(r["item_idx"], r["tag_vec"]) for r in rows], n_items, len(tag_model.vocabulary)))
    x_desc = l2_rows(_to_csr([(r["item_idx"], r["d_vec"]) for r in rows], n_items,
                             max(1, len(desc_model.vocabulary))))
    return {"X_tag": x_tag.tocsr(), "X_desc": x_desc.tocsr(), "tag_vocab": list(tag_model.vocabulary),
            "tag_idf": tag_idf.idf.toArray().astype(np.float32)}


def combine(x_tag: sparse.csr_matrix, x_desc: sparse.csr_matrix, w_tag: float, w_desc: float) -> sparse.csr_matrix:
    parts = [w_tag * x_tag] + ([w_desc * x_desc] if w_desc > 0 else [])
    return l2_rows(sparse.hstack(parts).tocsr()).astype(np.float32).tocsr()


def item_knn(x: sparse.csr_matrix, n_neighbors: int, block: int = 512) -> sparse.csr_matrix:
    """Top-N cosine neighbors per item (self excluded). Output CSR [n_items, n_items]."""
    n = x.shape[0]
    xt = x.T.tocsc()
    rows, cols, vals = [], [], []
    for s in range(0, n, block):
        e = min(n, s + block)
        sim = np.asarray((x[s:e] @ xt).todense(), np.float32)
        sim[np.arange(e - s), np.arange(s, e)] = 0.0
        kk = min(n_neighbors, n - 1)
        top = np.argpartition(-sim, kk - 1, axis=1)[:, :kk]
        tv = np.take_along_axis(sim, top, axis=1)
        keep = tv > 0
        rr = np.repeat(np.arange(s, e), kk).reshape(e - s, kk)
        rows.append(rr[keep])
        cols.append(top[keep])
        vals.append(tv[keep])
    return sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
