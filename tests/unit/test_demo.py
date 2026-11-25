"""Demo serving: fallback paths must not recommend games the user already reviewed."""


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
