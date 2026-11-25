"""Web backend adapter (web/backend/main.py) over the fake demo lake. Needs the 'web' group:
uv run --group web pytest tests/unit/test_web_backend.py"""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

MAIN = Path(__file__).resolve().parents[2] / "web" / "backend" / "main.py"


@pytest.fixture
def client(demo, monkeypatch):
    spec = importlib.util.spec_from_file_location("web_backend_main", MAIN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "K", 2)  # demo fixture has k=3 = K+1
    m.init(demo)
    return TestClient(m.app)  # no `with`: lifespan (real lake) is not run


def test_tags_hide_genre_and_category_tokens(client):
    assert client.get("/api/tags").json() == ["a"]
    assert client.get("/api/genres").json() == ["g_action"]


def test_health_has_known_sample(client):
    h = client.get("/api/health").json()
    assert h["known_sample"] == [7] and h["users"] == 1


def test_unknown_user_fallback_respects_exclude(client):
    res = client.get("/api/recommend/999", params={"exclude": [100, 102]}).json()
    assert res["mode"] == "fallback:popularity (history-masked)"
    assert [r["app_id"] for r in res["items"]] == [101, 103]
    assert [r["rank"] for r in res["items"]] == [1, 2]


def test_known_user_precomputed(client):
    res = client.get("/api/recommend/7", params={"model": "als"}).json()
    assert res["mode"] == "precomputed:als"
    assert [r["app_id"] for r in res["items"]] == [100, 101]


def test_genre_token_works_as_cold_start_tag(client):
    res = client.get("/api/recommend/tags", params={"tags": ["g_action"]}).json()
    assert res["mode"] == "cold-start:tags"
    assert {r["app_id"] for r in res["items"]} <= {100, 101, 102}


def test_game_404_and_similar_drops_itself(client):
    assert client.get("/api/games/9999").status_code == 404
    res = client.get("/api/games/100/similar").json()
    assert 100 not in [r["app_id"] for r in res["items"]] and len(res["items"]) == 2
