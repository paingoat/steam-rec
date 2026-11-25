"""FastAPI backend cho web demo: adapter mỏng quanh steam_rec.serving.demo.Demo (xem docs/web-demo.md).

Không sửa src/steam_rec/. Những gì Demo chưa có (tìm theo tên, chi tiết game, game tương tự) viết ở đây.
Chạy từ gốc repo:  uv run --group web uvicorn main:app --app-dir web/backend --port 8000
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

K = int(os.environ.get("STEAM_REC_K", "10"))
ORIGINS = os.environ.get("STEAM_REC_CORS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
Model = Literal["als", "cb", "popularity"]

state: dict = {}


def find_run(lake: Path) -> str:
    """Như serving.demo.latest_run nhưng đọc thẳng thư mục: latest_run tách key theo '/', trên Windows
    LocalStore.list trả '\\' nên không thấy run nào. Ưu tiên run full mới nhất."""
    runs = sorted(p.parent.parent.name for p in (lake / "artifacts").glob("*/stages/recommend.json"))
    if not runs:
        raise SystemExit(f"no run with a finished 'recommend' stage in {lake}; run scripts/demo/fetch_bundle.py")

    def scale(r: str) -> str | None:
        f = lake / "artifacts" / r / "run.json"
        return json.loads(f.read_text(encoding="utf-8")).get("scale") if f.exists() else None

    full = [r for r in runs if scale(r) == "full"]
    return (full or runs)[-1]


@asynccontextmanager
async def lifespan(_: FastAPI):
    if sys.platform == "win32" and not sys.flags.utf8_mode:
        # load_config đọc yaml (có comment tiếng Việt) bằng encoding mặc định của hệ điều hành
        raise SystemExit("On Windows run with PYTHONUTF8=1 (see web/backend/README.md)")
    from steam_rec.common.config import load_config
    from steam_rec.serving.demo import Demo
    from steam_rec.storage.store import get_store

    cfg = load_config("demo")
    run_id = os.environ.get("STEAM_REC_RUN_ID") or find_run(cfg.resolve_path(cfg.storage.local_root))
    # k+1 để /similar còn đủ K sau khi bỏ chính game đó; các endpoint khác cắt còn K
    demo = Demo(cfg, get_store(cfg), run_id=run_id, k=K + 1)
    cat = demo.catalog
    state.update(demo=demo, by_app={int(a): int(i) for i, a in cat["app_id"].items()})
    yield
    state.clear()


app = FastAPI(title="steam-rec web API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET"], allow_headers=["*"])


def game_row(item_idx: int) -> dict:
    g = state["demo"].catalog.loc[item_idx]
    return {"app_id": int(g.app_id), "title": g.title, "rating": g.rating, "positive_ratio": int(g.positive_ratio),
            "price_final": float(g.price_final), "tags": [str(t) for t in (g.tags if g.tags is not None else [])]}


def finish(res: dict, exclude: int | None = None) -> dict:
    """Bỏ game bị loại, cắt còn K, đánh lại rank, thêm price_final/positive_ratio từ catalog."""
    cat, by_app = state["demo"].catalog, state["by_app"]
    items = [it for it in res["items"] if it["app_id"] != exclude][:K]
    for rank, it in enumerate(items, 1):
        g = cat.loc[by_app[it["app_id"]]]
        it.update(rank=rank, tags=[str(t) for t in it["tags"]], price_final=float(g.price_final),
                  positive_ratio=int(g.positive_ratio))
    return {**res, "items": items}


@app.get("/api/health")
def health() -> dict:
    d = state["demo"]
    return {"ok": True, "run_id": d.run_id, "games": len(d.catalog), "users": len(d.known), "k": K}


@app.get("/api/users/{user_id}")
def user(user_id: int) -> dict:
    return {"user_id": user_id, "known": user_id in state["demo"].known}


# Khai báo trước /api/recommend/{user_id} để "tags" không bị hiểu là user_id
@app.get("/api/recommend/tags")
def recommend_tags(tags: Annotated[list[str] | None, Query()] = None) -> dict:
    return finish(state["demo"].for_new_user([t for t in tags or [] if t.strip()]))


@app.get("/api/recommend/{user_id}")
def recommend_user(user_id: int, model: Model = "als") -> dict:
    return finish(state["demo"].for_user(user_id, model=model))


@app.get("/api/games")
def search(q: str = "", limit: Annotated[int, Query(ge=1, le=50)] = 20) -> list[dict]:
    d, needle = state["demo"], q.strip().lower()
    if not needle:
        return []
    hits = d.catalog.index[d.catalog["title"].str.lower().str.contains(needle, regex=False)]
    hits = sorted(hits, key=lambda i: -d.pop[i])[:limit]  # game phổ biến lên trước
    return [game_row(int(i)) for i in hits]


@app.get("/api/games/{app_id}")
def game(app_id: int) -> dict:
    if app_id not in state["by_app"]:
        raise HTTPException(404, f"app_id {app_id} not in catalog")
    return game_row(state["by_app"][app_id])


@app.get("/api/games/{app_id}/similar")
def similar(app_id: int) -> dict:
    g = game(app_id)
    return finish(state["demo"].for_new_user(g["tags"]), exclude=app_id)


@app.get("/api/tags")
def tags() -> list[str]:
    return list(state["demo"].tag_vocab)
