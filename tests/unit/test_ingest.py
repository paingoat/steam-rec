from steam_rec.common.config import load_config
from steam_rec.ingestion.kaggle import ingest, verify_against_manifest
from steam_rec.storage.store import LocalStore


def test_ingest_idempotent(tmp_path):
    cfg = load_config("local", "smoke", overrides={"dataset": {"files": ["a.csv", "b.json"]}})
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.csv").write_text("x,y\n1,2\n")
    (raw / "b.json").write_text('{"k":1}\n')
    store = LocalStore(tmp_path / "lake")
    m1 = ingest(cfg, store, raw)
    m2 = ingest(cfg, store, raw)
    assert m1["ingest_run_id"] == m2["ingest_run_id"]
    assert len([k for k in store.list("bronze") if k.endswith("_manifest.json")]) == 1
    assert verify_against_manifest(raw, m1) == []
    (raw / "a.csv").write_text("changed\n")
    assert verify_against_manifest(raw, m1) == ["a.csv"]
