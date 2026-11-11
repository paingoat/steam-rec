import datetime as dt

from pyspark.sql import functions as F

from steam_rec.features.cf_interactions import kcore
from steam_rec.features.splits import leave_last_out
from steam_rec.pipelines.silver import dedup_user_app, sample_users


def _d(s):
    return dt.date.fromisoformat(s)


def test_leave_last_out_temporal_no_leakage(spark):
    rows = [  # user 1: 4 positives, two on the same last date (tie broken by review_id)
        (1, 10, _d("2020-01-01"), 1), (1, 11, _d("2020-02-01"), 2), (1, 12, _d("2020-03-01"), 3),
        (1, 13, _d("2020-03-01"), 4),
        (2, 10, _d("2021-01-01"), 5), (2, 11, _d("2021-01-02"), 6),  # only 2 positives -> all train
    ]
    df = spark.createDataFrame(rows, "user_id long, app_id int, date date, review_id long")
    out = {(r.user_id, r.app_id): r.split for r in leave_last_out(df, 3).collect()}
    assert out[(1, 13)] == "test" and out[(1, 12)] == "val"
    assert out[(1, 10)] == out[(1, 11)] == "train"
    assert out[(2, 10)] == out[(2, 11)] == "train"
    # leakage guard: every train row strictly precedes the user's val row, val precedes test
    s = leave_last_out(df, 3).withColumn("k", F.struct("date", "review_id"))
    agg = s.groupBy("user_id").pivot("split", ["train", "val", "test"]).agg(F.max("k")).collect()
    for r in agg:
        if r.val is not None:
            assert r.train < r.val < r.test


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
