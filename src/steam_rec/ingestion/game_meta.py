"""Game-metadata enrichment → Bronze `bronze/game_meta/<source>-<tag>/` (immutable, SHA-256 manifest).

Kaggle v28 `games_metadata.json` has empty `tags`/`description` for many of the MOST played games (TF2, CS:GO, Witcher 3…:
51% of positive reviews fall on tag-less games). Two sources fill the gaps:

* **HF `FronkonGames/steam-games-dataset`** (MIT, pinned revision): `short_description`, `genres`, `categories`,
  `developers`, `publishers`. Its `tags` column is all-null, so it is not used for tags. Only the needed columns are read
  from the remote parquet (HTTP range requests via DuckDB, ≈20 MB instead of the 192 MB file), filtered to v28 app_ids.
* **SteamSpy `appdetails`** (≤1 req/s): community tags ordered by votes, only for v28 games whose tags are empty.

Run locally (`steam-rec ingest-meta`); the resulting Bronze is small and is uploaded to Colab with the code.
"""

from __future__ import annotations

import json
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from steam_rec.common.config import Config
from steam_rec.common.logging import LOG, phase
from steam_rec.common.run_id import utc_now
from steam_rec.pipelines.bronze_reader import bronze_manifest
from steam_rec.storage import paths
from steam_rec.storage.store import Store, sha256_file

HF_REPO = "FronkonGames/steam-games-dataset"
HF_REVISION = "6c21457b9ebf0a6a7f5b91e11281d65d456ea30e"  # 2026-11-08, license MIT
HF_FILE = "data/train-00000-of-00001.parquet"
HF_COLUMNS = ["short_description", "genres", "categories", "developers", "publishers"]
STEAMSPY_URL = "https://steamspy.com/api.php?request=appdetails&appid={app_id}"
USER_AGENT = "steam-rec-research/0.1 (metadata enrichment; low rate)"


def hf_url(revision: str = HF_REVISION) -> str:
    return f"https://huggingface.co/datasets/{HF_REPO}/resolve/{revision}/{HF_FILE}"


# ---------- v28 inputs ----------

def load_v28(cfg: Config, store: Store) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games[app_id, title, user_reviews], meta[app_id, description, tags]) from the latest Kaggle Bronze snapshot."""
    man = bronze_manifest(cfg, store)
    v, run = cfg.dataset.version, man["ingest_run_id"]
    with tempfile.TemporaryDirectory() as d:
        g, m = Path(d) / "games.csv", Path(d) / "games_metadata.json"
        store.get_file(paths.bronze_raw(v, run, "games.csv"), g)
        store.get_file(paths.bronze_raw(v, run, "games_metadata.json"), m)
        games = pd.read_csv(g, usecols=["app_id", "title", "user_reviews"])
        meta = pd.read_json(m, lines=True)
    return games, meta


def steamspy_targets(games: pd.DataFrame, meta: pd.DataFrame) -> list[int]:
    """v28 games with no tags, most-reviewed first (Steam `user_reviews` is a cheap proxy for interaction volume)."""
    empty = meta[meta["tags"].map(lambda t: t is None or len(t) == 0)][["app_id"]]
    t = empty.merge(games[["app_id", "user_reviews"]], on="app_id", how="left").fillna({"user_reviews": 0})
    return t.sort_values(["user_reviews", "app_id"], ascending=[False, True])["app_id"].astype(int).tolist()


# ---------- parsing (pure, unit-tested) ----------

def parse_steamspy(app_id: int, payload: dict | None) -> dict:
    """SteamSpy appdetails → {app_id, tags (by votes desc), status}. `tags` is a dict {tag: votes} or [] when unknown."""
    if not payload or not payload.get("name"):
        return {"app_id": app_id, "tags": [], "status": "not_found"}
    raw = payload.get("tags") or {}
    tags = [k for k, _ in sorted(raw.items(), key=lambda kv: (-int(kv[1]), kv[0]))] if isinstance(raw, dict) else []
    return {"app_id": app_id, "tags": tags, "status": "ok" if tags else "no_tags"}


# ---------- sources ----------

def fetch_hf(app_ids: list[int], revision: str = HF_REVISION) -> pd.DataFrame:
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.register("ids", pd.DataFrame({"app_id": app_ids}))
    cols = ", ".join(f"h.{c}" for c in HF_COLUMNS)
    with phase("meta.hf", revision=revision[:8]):
        df = con.execute(f"""SELECT CAST(h.appID AS INTEGER) AS app_id, {cols}
                             FROM read_parquet('{hf_url(revision)}') h
                             JOIN ids ON CAST(h.appID AS INTEGER) = ids.app_id""").df()
    for c in ("genres", "categories", "developers", "publishers"):
        df[c] = df[c].map(lambda x: [] if x is None else [str(v) for v in x])
    return df.drop_duplicates("app_id")


def fetch_steamspy(app_ids: list[int], cache: Path, rate_s: float = 1.05, retries: int = 3) -> pd.DataFrame:
    """Resumable: every response is appended to `cache` (JSONL); already-cached app_ids are skipped."""
    done: dict[int, dict] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            r = json.loads(line)
            done[r["app_id"]] = r
    todo = [a for a in app_ids if a not in done]
    LOG.info("steamspy: %s targets, %s cached, %s to fetch (~%.0f min)", len(app_ids), len(done), len(todo),
             len(todo) * rate_s / 60)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("a") as f, phase("meta.steamspy", n=len(todo)):
        for i, a in enumerate(todo, 1):
            rec = {"app_id": a, "tags": [], "status": "error"}
            for attempt in range(retries):
                try:
                    req = urllib.request.Request(STEAMSPY_URL.format(app_id=a), headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        rec = parse_steamspy(a, json.loads(resp.read().decode()))
                    break
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                    LOG.warning("steamspy %s attempt %s: %s", a, attempt + 1, e)
                    time.sleep(5 * (attempt + 1))
            f.write(json.dumps(rec) + "\n")
            f.flush()
            done[a] = rec
            if i % 100 == 0:
                LOG.info("steamspy %s/%s", i, len(todo))
            time.sleep(rate_s)
    return pd.DataFrame([done[a] for a in app_ids if a in done], columns=["app_id", "tags", "status"])


# ---------- Bronze publish ----------

def _publish(store: Store, source: str, tag: str, df: pd.DataFrame, extra: dict) -> dict:
    prefix = paths.bronze_meta_prefix(source, tag)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"{source}.parquet"
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), p, compression="zstd")
        key = f"{prefix}/raw/{source}.parquet"
        store.put_file(p, key)
        entry = {"name": p.name, "key": key, "size": p.stat().st_size, "sha256": sha256_file(p)}
    man = {"source": source, "tag": tag, "ingested_at": utc_now().isoformat(), "rows": len(df), "files": [entry], **extra}
    store.put_text(f"{prefix}/_manifest.json", json.dumps(man, indent=2))
    return man


def ingest_meta(cfg: Config, store: Store, skip_steamspy: bool = False, limit: int | None = None,
                skip_hf: bool = False) -> dict:
    games, meta = load_v28(cfg, store)
    out = {}
    if not skip_hf:
        hf = fetch_hf(games["app_id"].astype(int).tolist())
        out["hf"] = _publish(store, "hf", HF_REVISION[:8], hf,
                             {"repo": HF_REPO, "revision": HF_REVISION, "columns": HF_COLUMNS, "license": "MIT",
                              "v28_games": len(games), "matched": len(hf)})
    if not skip_steamspy:
        targets = steamspy_targets(games, meta)[:limit]
        ss = fetch_steamspy(targets, cfg.resolve_path(cfg.storage.staging_dir) / "steamspy_cache.jsonl")
        out["steamspy"] = _publish(store, "steamspy", f"{utc_now():%Y%m%d}", ss,
                                   {"url": STEAMSPY_URL, "targets": len(targets),
                                    "status": ss["status"].value_counts().to_dict()})
    latest = {k: v["tag"] for k, v in out.items()}
    if store.exists(paths.bronze_meta_latest()):  # keep the other source's pointer when only one is refreshed
        latest = {**json.loads(store.get_text(paths.bronze_meta_latest())), **latest}
    store.put_text(paths.bronze_meta_latest(), json.dumps(latest))
    LOG.info("game_meta bronze published: %s", latest)
    return {k: {"tag": v["tag"], "rows": v["rows"]} for k, v in out.items()}
