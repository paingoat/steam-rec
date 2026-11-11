import math

import numpy as np
from scipy import sparse

from steam_rec.evaluation.metrics import ndcg_at_k, recall_at_k, spark_metrics
from steam_rec.models.cb_tfidf import combine, item_knn, l2_rows
from steam_rec.models.scoring import _topk_rows


def test_recall_ndcg_reference():
    recs = [5, 3, 9]
    assert recall_at_k(recs, 3, 2) == 1.0 and recall_at_k(recs, 9, 2) == 0.0
    assert math.isclose(ndcg_at_k(recs, 5, 3), 1.0)
    assert math.isclose(ndcg_at_k(recs, 9, 3), 1 / math.log2(4))


def test_spark_metrics_match_reference(spark):
    rows = [(0, [5, 3, 9], 3), (1, [1, 2, 4], 7), (2, [7], 7)]
    df = spark.createDataFrame(rows, "user_idx int, items array<int>, t int")
    m = spark_metrics(df, "t", [2, 3], n_items=10)
    assert math.isclose(m["recall@2"], 2 / 3, rel_tol=1e-5)
    assert math.isclose(m["ndcg@3"], (1 / math.log2(3) + 0 + 1) / 3, rel_tol=1e-5)
    assert math.isclose(m["eligible_user_coverage@3"], 2 / 3, rel_tol=1e-5)
    assert math.isclose(m["catalog_coverage@2"], 5 / 10)  # {5,3,1,2,7}


def test_topk_masks_seen_and_orders():
    scores = np.array([[0.1, 0.9, 0.5, 0.7]], np.float32)
    items, vals = next(_topk_rows(scores.copy(), [[1]], 2))
    assert items == [3, 2] and vals[0] > vals[1]
    items, _ = next(_topk_rows(scores.copy(), [[0, 1, 2, 3]], 2))
    assert items == []  # everything masked -> fewer than K, counted by eligible_user_coverage


def test_item_knn_excludes_self_and_is_cosine():
    x = l2_rows(sparse.csr_matrix(np.array([[1, 0], [1, 1], [0, 1]], np.float32)))
    s = item_knn(x.tocsr(), n_neighbors=1, block=2).toarray()
    assert np.all(np.diag(s) == 0)
    assert s[0].argmax() == 1 and math.isclose(s[0, 1], 1 / math.sqrt(2), rel_tol=1e-5)


def test_combine_weights_zero_desc_ignores_desc():
    xt = sparse.csr_matrix(np.eye(2, dtype=np.float32))
    xd = sparse.csr_matrix(np.ones((2, 3), np.float32))
    c = combine(xt, xd, 1.0, 0.0)
    assert c.shape == (2, 2)
