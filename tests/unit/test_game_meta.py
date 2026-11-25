"""Metadata enrichment: SteamSpy parsing, target ordering, Silver merge precedence, CB tokens (no network)."""

import pandas as pd

from steam_rec.ingestion.game_meta import parse_steamspy, steamspy_targets


def test_parse_steamspy_orders_by_votes():
    r = parse_steamspy(440, {"name": "TF2", "tags": {"FPS": 10, "Free to Play": 30, "Action": 10}})
    assert r == {"app_id": 440, "tags": ["Free to Play", "Action", "FPS"], "status": "ok"}
    assert parse_steamspy(1, {"name": "", "tags": []})["status"] == "not_found"
    assert parse_steamspy(2, {"name": "X", "tags": []}) == {"app_id": 2, "tags": [], "status": "no_tags"}


def test_steamspy_targets_only_tagless_most_reviewed_first():
    games = pd.DataFrame({"app_id": [1, 2, 3], "title": list("abc"), "user_reviews": [5, 100, 50]})
    meta = pd.DataFrame({"app_id": [1, 2, 3], "description": ["", "", ""], "tags": [[], [], ["RPG"]]})
    assert steamspy_targets(games, meta) == [2, 1]


def test_enrich_meta_precedence(spark):
    from steam_rec.pipelines.silver import enrich_meta

    meta = spark.createDataFrame(
        [(1, "own desc", ["RPG"]), (2, None, []), (3, None, [])],
        "app_id int, description string, tags array<string>")
    hf = spark.createDataFrame(
        [(1, "hf1", ["Action"], ["Single-player"], ["D"], ["P"]), (2, "hf2", ["Indie"], [], [], [])],
        "app_id int, short_description string, genres array<string>, categories array<string>, "
        "developers array<string>, publishers array<string>")
    ss = spark.createDataFrame([(1, ["Shooter"]), (2, ["FPS", "PvP"])], "app_id int, tags array<string>")
    out = {r.app_id: r for r in enrich_meta(meta, hf, ss).collect()}
    assert out[1].tags == ["RPG"] and out[1].tags_src == "v28"          # v28 wins
    assert out[1].description == "own desc" and out[1].desc_src == "v28"
    assert out[2].tags == ["FPS", "PvP"] and out[2].tags_src == "steamspy"
    assert out[2].description == "hf2" and out[2].desc_src == "hf" and out[2].genres == ["Indie"]
    assert out[3].tags == [] and out[3].tags_src == "none" and out[3].desc_src == "none"
    assert out[3].genres == [] and out[3].publishers == []
    # without enrichment sources: v1 behaviour, empty lists
    plain = {r.app_id: r for r in enrich_meta(meta).collect()}
    assert plain[2].tags == [] and plain[2].genres == [] and plain[1].tags_src == "v28"


def test_tag_tokens_prefix_extra_fields(spark):
    from steam_rec.models.cb_tfidf import tag_tokens

    df = spark.createDataFrame([(["Open World", "Action"], ["Action"], ["Co-op"])],
                               "tags array<string>, genres array<string>, categories array<string>")
    toks = df.select(tag_tokens(df, ["genres", "categories", "missing"]).alias("t")).first().t
    assert toks == ["open_world", "action", "g_action", "c_co_op"]
    assert df.select(tag_tokens(df, []).alias("t")).first().t == ["open_world", "action"]
