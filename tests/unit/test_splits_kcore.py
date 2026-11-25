import datetime as dt

from pyspark.sql import functions as F

from steam_rec.features.cf_interactions import kcore
from steam_rec.features.splits import global_time_split
from steam_rec.pipelines.silver import dedup_user_app, sample_users


def _d(s):
    return dt.date.fromisoformat(s)


def test_global_time_split_no_cross_user_leakage(spark):
    rows = [(1, 10, _d("2022-01-01"), 1), (1, 11, _d("2022-08-15"), 2), (1, 12, _d("2022-10-01"), 3),
            (2, 10, _d("2022-09-30"), 4), (2, 13, _d("2022-12-31"), 5), (3, 14, _d("2022-06-30"), 6)]
    df = spark.createDataFrame(rows, "user_id long, app_id int, date date, review_id long")
    out = global_time_split(df, "2022-07-01", "2022-10-01")
    got = {(r.user_id, r.app_id): r.split for r in out.collect()}
    assert got == {(1, 10): "train", (1, 11): "val", (1, 12): "test", (2, 10): "val", (2, 13): "test",
                   (3, 14): "train"}
    # one global cut-off: every train row precedes every val row, which precedes every test row (across users)
    b = {r.split: (r.lo, r.hi) for r in out.groupBy("split").agg(F.min("date").alias("lo"),
                                                                 F.max("date").alias("hi")).collect()}
    assert b["train"][1] < _d("2022-07-01") <= b["val"][0] and b["val"][1] < _d("2022-10-01") <= b["test"][0]


def test_global_time_split_rejects_bad_order(spark):
    import pytest

    df = spark.createDataFrame([(1, _d("2022-01-01"))], "user_id long, date date")
    with pytest.raises(ValueError):
        global_time_split(df, "2022-10-01", "2022-07-01")


def test_kcore_on_train_ignores_future(spark):
    """k-core must see train only: an item kept alive by val/test interactions alone is dropped."""
    train = [(u, 1) for u in range(3)] + [(u, 2) for u in range(3)] + [(0, 3)]
    future = [(u, 3) for u in range(1, 3)]  # would lift item 3 to 3 users if counted
    df = spark.createDataFrame(train + future, "user_id long, app_id int")
    core_all, _ = kcore(df, 1, 3)
    core_train, _ = kcore(spark.createDataFrame(train, "user_id long, app_id int"), 1, 3)
    assert 3 in {r.app_id for r in core_all.collect()}
    assert 3 not in {r.app_id for r in core_train.collect()}


def test_kcore_converges(spark):
    rows = [(u, i) for u in range(5) for i in range(3)] + [(99, 0)]  # user 99 has 1 interaction
    df = spark.createDataFrame(rows, "user_id long, app_id int")
    core, rounds = kcore(df, 2, 3)
    assert rounds > 0 and 99 not in {r.user_id for r in core.select("user_id").distinct().collect()}
    assert core.count() == 15


def test_dedup_keeps_latest(spark):
    rows = [(1, 10, _d("2020-01-01"), 1), (1, 10, _d("2021-01-01"), 2), (1, 11, _d("2020-01-01"), 3)]
    df = spark.createDataFrame(rows, "user_id long, app_id int, date date, review_id long")
    assert sorted(r.review_id for r in dedup_user_app(df).collect()) == [2, 3]


def test_sample_users_keeps_whole_histories(spark):
    df = spark.range(0, 2000).select((F.col("id") % 200).alias("user_id"), F.col("id").alias("x"))
    s = sample_users(df, 0.3, 42)
    per_user = {r.user_id: r["count"] for r in s.groupBy("user_id").count().collect()}
    assert all(c == 10 for c in per_user.values()) and 20 < len(per_user) < 100
    assert s.count() == sample_users(df, 0.3, 42).count()  # deterministic


def test_orphan_keys_detects_missing_users(spark):
    from steam_rec.pipelines.silver import orphan_keys

    recs = spark.createDataFrame([(1, 10), (2, 10), (3, 11), (3, 12)], "user_id long, app_id int")
    users = spark.createDataFrame([(1,), (2,)], "user_id long")
    assert orphan_keys(recs, users, "user_id") == 1
    assert orphan_keys(recs.filter("user_id < 3"), users, "user_id") == 0
