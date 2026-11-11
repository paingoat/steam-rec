from steam_rec.common.config import deep_merge, load_config
from steam_rec.common.run_id import new_run_id
from steam_rec.storage import paths


def test_merge_env_and_scale():
    cfg = load_config("colab", "full")
    assert cfg.execution == "colab"
    assert cfg.storage.backend == "local"
    assert cfg.scale.max_recommendations is None
    assert cfg.spark.shuffle_partitions == 128
    assert cfg.dataset.version == 28


def test_config_hash_changes_with_scale():
    assert load_config("local", "smoke").config_hash() != load_config("local", "dev").config_hash()
    assert load_config("local", "smoke").config_hash() == load_config("local", "smoke").config_hash()


def test_deep_merge_nested():
    assert deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"c": 3}}) == {"a": {"b": 1, "c": 3}}


def test_run_id_format():
    rid = new_run_id("abcd1234")
    assert rid.endswith("-abcd1234") and rid[8] == "T"


def test_paths_layout():
    assert paths.bronze_raw(28, "r1", "games.csv") == "bronze/kaggle/v28/r1/raw/games.csv"
    assert paths.silver("games", 28, "r2") == "silver/games/dataset=v28/run=r2"
    assert paths.success_marker("gold/x/") == "gold/x/_SUCCESS"
