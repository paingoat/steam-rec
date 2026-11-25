# steam-rec web backend

FastAPI adapter around `steam_rec.serving.demo.Demo` (see `docs/web-demo.md`). It serves the API contract in
`web/frontend/README.md`. Dependencies live in the `web` dependency group, not in `[project].dependencies`.

```bash
# from the repo root, once
uv run --with huggingface_hub python scripts/demo/fetch_bundle.py

# run (http://localhost:8000, docs at /docs)
uv run --group web uvicorn main:app --app-dir web/backend --port 8000
```

On Windows (PowerShell), `.\web\backend\run.ps1` does the same with `PYTHONUTF8=1` and auto-reload, from any folder.

`Demo` is created once at startup, so the first request is not slow. The first start copies parquet files to
`data/cache/<run_id>/`.

## Windows

Two things are needed on Windows only, and both are handled without touching `src/steam_rec/`:

- **`PYTHONUTF8=1` is required.** `load_config` reads the yaml configs with the OS default encoding (cp1258/cp1252),
  and the Vietnamese comments in those files fail to decode. The app exits with a clear message if it is missing.
  - PowerShell: `$env:PYTHONUTF8=1; uv run --group web uvicorn main:app --app-dir web/backend --port 8000`
  - Git Bash: `PYTHONUTF8=1 uv run --group web uvicorn ...`
- **The run is found by `find_run()`.** `Demo`'s own `latest_run` splits store keys on `/`, and `LocalStore.list`
  returns `\` on Windows, so it finds no run. `find_run()` scans `data/lake/artifacts/*/stages/recommend.json` instead.
  Like `latest_run`, it prefers the newest full run.

## Settings (env vars)

| var | default | meaning |
|---|---|---|
| `STEAM_REC_RUN_ID` | newest full run in `data/lake` | pin a run |
| `STEAM_REC_K` | `10` | items per list |
| `STEAM_REC_CORS` | `http://localhost:3000,http://127.0.0.1:3000` | allowed frontend origins (comma-separated) |

## Endpoints

| Endpoint | Notes |
|---|---|
| `GET /api/health` | `run_id`, number of games/users, `k` |
| `GET /api/users/{user_id}` | `{user_id, known}` |
| `GET /api/recommend/{user_id}?model=als\|cb\|popularity` | `demo.for_user`, unknown user → popularity fallback |
| `GET /api/recommend/tags?tags=a&tags=b` | `demo.for_new_user`, raw ("Open World") or normalized ("open_world") tags |
| `GET /api/games/{app_id}` | catalog row with all tags, 404 if unknown |
| `GET /api/games/{app_id}/similar` | the game's tags → `for_new_user` with k+1, the game itself dropped |
| `GET /api/games?q=&limit=20` | case-insensitive title search, most popular first |
| `GET /api/tags` | `demo.tag_vocab` (normalized) |

Every list item also carries `price_final` and `positive_ratio` from the catalog. `Demo` is built with `k+1` so
`/similar` still has K items after dropping the game, and every list is cut back to K.

**Data caveat:** many of the most popular games (ELDEN RING, The Witcher 3, Team Fortress 2, ...) have **empty tags**
in Kaggle v28. For them, `/similar` returns `mode: "fallback:popularity (no known tags)"`.
