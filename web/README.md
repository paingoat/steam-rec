# steam-rec web demo

Next.js frontend (`web/frontend`) + FastAPI backend (`web/backend`) around `steam_rec.serving.demo.Demo`.
Read `docs/web-demo.md` first. Details: `web/frontend/README.md`, `web/backend/README.md`.

## Run

```bash
# once, from the repo root: download the demo bundle into data/lake (not in git)
uv run --with huggingface_hub python scripts/demo/fetch_bundle.py

# terminal 1: backend  -> http://localhost:8000/docs
uv run --group web uvicorn main:app --app-dir web/backend --port 8000  # Windows: .\web\backend\run.ps1

# terminal 2: frontend -> http://localhost:3000
cd web/frontend && npm install && npm run dev
```

`web/frontend/.env.local` must contain `NEXT_PUBLIC_API_URL=http://localhost:8000`. Without it the site uses mock data
and shows a yellow "Mock data" badge.

## Known issues on Windows

The pipeline was written and tested on Ubuntu. The first two issues below were found while building the web and are
**fixed in core since v2** (suggested in the first version of this file); they have not been re-checked on a Windows
machine yet, so the old workarounds are kept as notes.

| Symptom | Cause | Status |
|---|---|---|
| `UnicodeDecodeError: 'charmap' codec can't decode byte ...` on any `steam-rec` / `fetch_bundle.py` command | `load_config` read the yaml configs with the OS code page | **Fixed in v2** (`read_text(encoding="utf-8")` in `common/config.py`, `storage/store.py`). Old workaround: `PYTHONUTF8=1` |
| `no run with a finished 'recommend' stage found in the lake`, although `data/lake/artifacts/<run_id>/` exists | `LocalStore.list` returned keys with `\` on Windows | **Fixed in v2** (`as_posix()`). The backend still has `find_run()` as a fallback. Old workaround: `--run-id <run_id>` |
| `test_ingest_idempotent` fails with `No module named 'resource'` | Unix-only `resource` module in `common/logging.py` | **Fixed in v2** (returns 0 when missing) |
| Spark tests error at `setCheckpointDir` | Spark on Windows needs Hadoop `winutils.exe` | Not fixed: run the pipeline tests on Linux, WSL or Colab. The web does not need Spark |
| `run.ps1 cannot be loaded because running scripts is disabled` | PowerShell execution policy | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
