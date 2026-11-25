# steam-rec web backend

FastAPI adapter around `steam_rec.serving.demo.Demo` (see `docs/web-demo.md`). It serves the API contract in
`web/frontend/README.md`. Dependencies live in the `web` dependency group, not in `[project].dependencies`.

```bash
# from the repo root, once
uv run --with huggingface_hub python scripts/demo/fetch_bundle.py

# run (http://localhost:8000, docs at /docs)
uv run --group web uvicorn main:app --app-dir web/backend --port 8000
```

On Windows (PowerShell), `.\web\backend\run.ps1` does the same with auto-reload, from any folder.

`Demo` is created once at startup, so the first request is not slow. The first start copies parquet files to
`data/cache/<run_id>/`.

## Windows

Both Windows problems found while building the web (yaml read with the OS encoding, `LocalStore.list` returning `\`)
are **fixed in core since v2**, so `PYTHONUTF8=1` is no longer required (still harmless; not yet re-checked on a
Windows machine). `find_run()` stays as a fallback: it scans `data/lake/artifacts/*/stages/recommend.json` and, like
`latest_run`, prefers the newest full run.

## Settings (env vars)

| var | default | meaning |
|---|---|---|
| `STEAM_REC_RUN_ID` | newest full run in `data/lake` | pin a run |
| `STEAM_REC_K` | `10` | items per list |
| `STEAM_REC_CORS` | `http://localhost:3000,http://127.0.0.1:3000` | allowed frontend origins (comma-separated) |

## Endpoints

| Endpoint | Notes |
|---|---|
| `GET /api/health` | `run_id`, number of games/users, `k`, `known_sample` (4 users with a top-K, for the login page) |
| `GET /api/users/{user_id}` | `{user_id, known}` |
| `GET /api/recommend/{user_id}?model=als\|cb\|popularity&exclude=730&exclude=570` | `demo.for_user`; unknown user → popularity fallback that drops the `exclude` app_ids (games the web knows the user reviewed) |
| `GET /api/recommend/tags?tags=a&tags=b` | `demo.for_new_user`, raw ("Open World") or normalized ("open_world") tags, or genre tokens (`g_rpg`) |
| `GET /api/games/{app_id}` | catalog row with all tags, 404 if unknown |
| `GET /api/games/{app_id}/similar` | the game's tags → `for_new_user` with k+1, the game itself dropped |
| `GET /api/games?q=&limit=20` | case-insensitive title search, most popular first |
| `GET /api/tags` | `demo.tag_vocab` without the `g_`/`c_` tokens (normalized tags only) |
| `GET /api/genres` | the `g_*` tokens of `demo.tag_vocab`, minus software types and content labels |

Every list item also carries `price_final` and `positive_ratio` from the catalog. `Demo` is built with `k+1` so
`/similar` still has K items after dropping the game, and every list is cut back to K.

**Data note (v2):** the v1 caveat about popular games with empty tags is gone: the v2 catalog fills tags from SteamSpy,
and only 6 of 30,715 games have none (for those, `/similar` returns `mode: "fallback:popularity (no known tags)"`).
Tag-only similarity still favours niche games with the same tags; see the backlog.

Tests: `uv run --group web pytest tests/unit/test_web_backend.py` (fake lake, no data needed).
