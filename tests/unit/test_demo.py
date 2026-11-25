"""Demo serving: fallback paths must not recommend games the user already reviewed."""

import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from scipy import sparse

from steam_rec.storage.arrays import put_npy, put_npz
from steam_rec.storage.store import LocalStore

RUN = "20990101T000000Z-test"


def _write(store, tmp_path, key, table):
    f = tmp_path / "t.parquet"
    pq.write_table(table, f)
    store.put_file(f, f"artifacts/{RUN}/{key}/part-0.parquet")


@pytest.fixture
def demo(tmp_path, monkeypatch):
    import steam_rec.serving.demo as dm

    monkeypatch.setattr(dm, "CACHE", tmp_path / "cache")
    store = LocalStore(tmp_path / "lake")
    n = 6  # item_idx 0..5 -> app_id 100..105; popularity descending by item_idx
    _write(store, tmp_path, "catalog", pa.table({
        "item_idx": list(range(n)), "app_id": [100 + i for i in range(n)], "title": [f"g{i}" for i in range(n)],
        "rating": ["ok"] * n, "positive_ratio": [90] * n, "price_final": [0.0] * n, "tags": [["a"]] * n}))
    # known user 7: ALS top-K = 100, 101; popularity list = 102, 103, 104
    _write(store, tmp_path, "topk", pa.table({
        "user_id": [7] * 5, "app_id": [100, 101, 102, 103, 104], "rank": [1, 2, 1, 2, 3],
        "score": [0.9, 0.8, 5.0, 4.0, 3.0], "model": ["als", "als", "popularity", "popularity", "popularity"],
        "run_id": [RUN] * 5}))
    _write(store, tmp_path, "topk_users", pa.table({"user_id": [7], "user_idx": [0]}))
    put_npy(store, f"artifacts/{RUN}/models/popularity.npy", np.array([6, 5, 4, 3, 2, 1], np.float32))
    put_npz(store, f"artifacts/{RUN}/models/cb_x_tag.npz", sparse.csr_matrix(np.ones((n, 1), np.float32)))
    put_npy(store, f"artifacts/{RUN}/models/cb_tag_idf.npy", np.ones(1, np.float32))
    store.put_text(f"artifacts/{RUN}/models/cb_tag_vocab.json", json.dumps(["a"]))
    return dm.Demo(None, store, RUN, k=3)


def test_unknown_user_fallback_masks_history(demo):
    res = demo.for_user(999, exclude_app_ids=[100, 102])
    assert res["mode"] == "fallback:popularity (history-masked)"
    assert [r["app_id"] for r in res["items"]] == [101, 103, 104]


def test_unknown_user_without_history_gets_global_popularity(demo):
    res = demo.for_user(999)
    assert res["mode"] == "fallback:popularity (no history)"
    assert [r["app_id"] for r in res["items"]] == [100, 101, 102]


def test_known_user_backfill_respects_exclude(demo):
    res = demo.for_user(7, "als", exclude_app_ids=[101, 102])
    assert [r["app_id"] for r in res["items"]] == [100, 103, 104]
    assert [r["source"] for r in res["items"]] == ["als", "popularity-backfill", "popularity-backfill"]
