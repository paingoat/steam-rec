# steam-rec web demo

Next.js frontend (`web/frontend`) + FastAPI backend (`web/backend`) around `steam_rec.serving.demo.Demo`.
Read `docs/web-demo.md` first. Details: `web/frontend/README.md`, `web/backend/README.md`.

## Run

```bash
# once, from the repo root: download the demo bundle into data/lake (not in git)
uv run --with huggingface_hub python scripts/demo/fetch_bundle.py     # Windows: set PYTHONUTF8=1 first

# terminal 1: backend  -> http://localhost:8000/docs
uv run --group web uvicorn main:app --app-dir web/backend --port 8000  # Windows: .\web\backend\run.ps1

# terminal 2: frontend -> http://localhost:3000
cd web/frontend && npm install && npm run dev
```

`web/frontend/.env.local` must contain `NEXT_PUBLIC_API_URL=http://localhost:8000`. Without it the site uses mock data
and shows a yellow "Mock data" badge.

## Known issues on Windows

The pipeline code was written and tested on Ubuntu, so a few things assume Linux. This is not a problem with your
machine: any Windows machine hits them. The web works around them without touching `src/steam_rec/`.

| Symptom | Cause | Workaround |
|---|---|---|
| `UnicodeDecodeError: 'charmap' codec can't decode byte ...` when running any `steam-rec` / `fetch_bundle.py` command | `load_config` reads the yaml configs with `read_text()` and no encoding. On Windows that means the OS code page (cp1258/cp1252), and the Vietnamese comments fail to decode | Set `PYTHONUTF8=1` before the command. PowerShell: `$env:PYTHONUTF8=1`. Git Bash: `export PYTHONUTF8=1`. `run.ps1` sets it, and the backend refuses to start without it |
| `no run with a finished 'recommend' stage found in the lake`, although `data/lake/artifacts/<run_id>/` exists | `LocalStore.list` returns keys with `\` on Windows, and `latest_run` splits them on `/` | CLI: pass `--run-id <run_id>`. Backend: `find_run()` in `web/backend/main.py` scans the folder itself |
| `uv run pytest`: `test_local_store` fails, `test_ingest_idempotent` fails with `No module named 'resource'`, and the Spark tests error at `setCheckpointDir` | the same `\` keys, the Unix-only `resource` module in `common/logging.py`, and Spark on Windows needs Hadoop `winutils.exe` | None needed for the web: these tests cover the pipeline, not `web/`. Run the pipeline tests on Linux, WSL or Colab |
| `run.ps1 cannot be loaded because running scripts is disabled` | PowerShell execution policy | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |

### Suggested fixes in core (for the project owner, not done here)

- `src/steam_rec/common/config.py:87`: `path.read_text(encoding="utf-8")`. The same applies to `get_text`/`put_text`
  in `storage/store.py`.
- `src/steam_rec/storage/store.py:48`: `p.relative_to(self.root).as_posix()` instead of `str(...)`.
- `src/steam_rec/common/logging.py:21`: guard `import resource` and return 0 when it is not available.
