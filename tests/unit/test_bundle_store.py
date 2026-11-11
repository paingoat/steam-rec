import pytest

from steam_rec.storage.bundle import make_bundle, restore_bundle, verify_parts
from steam_rec.storage.store import LocalStore


def _mk(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.bin").write_bytes(b"x" * (3 * 1024 * 1024 + 7))
    (src / "sub" / "b.json").write_text('{"k": 1}')
    return src


def test_bundle_roundtrip(tmp_path):
    src = _mk(tmp_path)
    m = make_bundle(src, tmp_path / "out", "art", chunk_mb=1, meta={"run_id": "r"})
    assert len(m["parts"]) == 4
    assert verify_parts(tmp_path / "out") == []
    restore_bundle(tmp_path / "out", tmp_path / "dst")
    assert (tmp_path / "dst" / "a.bin").read_bytes() == (src / "a.bin").read_bytes()


def test_bundle_detects_corruption(tmp_path):
    make_bundle(_mk(tmp_path), tmp_path / "out", "art", chunk_mb=1)
    p = tmp_path / "out" / "art.tar.part0001"
    p.write_bytes(b"corrupt")
    assert verify_parts(tmp_path / "out") == ["art.tar.part0001"]
    with pytest.raises(ValueError):
        restore_bundle(tmp_path / "out", tmp_path / "dst")


def test_local_store(tmp_path):
    s = LocalStore(tmp_path / "lake")
    s.put_text("x/y/_SUCCESS", "")
    assert s.exists("x/y/_SUCCESS") and s.exists("x/y")
    assert s.list("x") == ["x/y/_SUCCESS"]
    assert s.uri("x").startswith("file://")
