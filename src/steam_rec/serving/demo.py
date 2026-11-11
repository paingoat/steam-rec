"""Offline demo: precomputed top-K for known users, content/popularity fallback for new users.

No Spark and no Colab: artifacts are pulled once from the lake (SILO or local) into data/cache/<run_id>/ and read
with pyarrow/numpy."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

from steam_rec.common.config import REPO_ROOT, Config
from steam_rec.storage import paths
from steam_rec.storage.arrays import get_npy, get_npz
from steam_rec.storage.store import Store

CACHE = REPO_ROOT / "data" / "cache"


RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-")


def latest_run(store: Store) -> str:
    """Newest timestamped run with a finished 'recommend' stage; full-scale runs win over smoke/dev."""
    runs = sorted({k.split("/")[1] for k in store.list("artifacts/") if k.endswith("stages/recommend.json")
                   and RUN_ID_RE.match(k.split("/")[1])})
    if not runs:
        raise SystemExit("no run with a finished 'recommend' stage found in the lake")
    full = [r for r in runs if store.exists(paths.artifacts(r, "run.json"))
            and json.loads(store.get_text(paths.artifacts(r, "run.json"))).get("scale") == "full"]
    return (full or runs)[-1]


class Demo:
    def __init__(self, cfg: Config, store: Store, run_id: str | None = None, k: int = 10):
        self.store, self.k = store, k
        self.run_id = run_id or latest_run(store)
        self.dir = CACHE / self.run_id
        for sub in ("topk", "catalog", "topk_users"):
            self._pull(paths.artifacts(self.run_id, sub))
        self.topk = pq.read_table(self.dir / "topk")
        self.catalog = pq.read_table(self.dir / "catalog").to_pandas().set_index("item_idx").sort_index()
        self.known = set(pq.read_table(self.dir / "topk_users").column("user_id").to_pylist())
        art = lambda *p: paths.artifacts(self.run_id, *p)
        self.pop = get_npy(store, art("models", "popularity.npy"))
        self.x_tag = get_npz(store, art("models", "cb_x_tag.npz"))
        self.tag_idf = get_npy(store, art("models", "cb_tag_idf.npy"))
        self.tag_vocab = {t: i for i, t in enumerate(json.loads(store.get_text(art("models", "cb_tag_vocab.json"))))}

    def _pull(self, prefix: str) -> None:
        for key in self.store.list(prefix + "/"):
            if key.endswith(".parquet"):
                dst = self.dir / key[len(paths.artifacts(self.run_id)) + 1:]
                if not dst.exists():
                    self.store.get_file(key, dst)

    def _rows(self, item_idx: list[int], scores: list[float], source: str) -> list[dict]:
        out = []
        for rank, (i, s) in enumerate(zip(item_idx, scores, strict=True), 1):
            g = self.catalog.loc[i]
            out.append({"rank": rank, "app_id": int(g.app_id), "title": g.title, "score": round(float(s), 4),
                        "rating": g.rating, "tags": list(g.tags[:5]) if g.tags is not None else [],
                        "source": source})
        return out

    def popular(self, exclude: set[int] = frozenset()) -> list[tuple[int, float]]:
        order = np.argsort(-self.pop)
        return [(int(i), float(self.pop[i])) for i in order if int(i) not in exclude][: self.k]

    def for_user(self, user_id: int, model: str = "als") -> dict:
        if user_id not in self.known:
            ids, sc = zip(*self.popular(), strict=True)
            return {"user_id": user_id, "mode": "fallback:popularity (user has no precomputed top-K)",
                    "items": self._rows(list(ids), list(sc), "popularity")}
        t = self.topk.filter(pc.and_(pc.equal(self.topk["user_id"], user_id), pc.equal(self.topk["model"], model)))
        t = t.sort_by("rank").to_pandas().head(self.k)
        app2idx = {int(a): int(i) for i, a in self.catalog["app_id"].items()}
        idx, sc, src = [app2idx[int(a)] for a in t.app_id], list(t.score), [model] * len(t)
        if len(idx) < self.k:
            # CB can be short when the user's history items lack tags/description -> backfill from this user's
            # precomputed popularity list (already masks everything the user has reviewed)
            p = self.topk.filter(pc.and_(pc.equal(self.topk["user_id"], user_id),
                                         pc.equal(self.topk["model"], "popularity"))).sort_by("rank").to_pandas()
            for a, s in zip(p.app_id, p.score, strict=True):
                if len(idx) >= self.k:
                    break
                if app2idx[int(a)] not in idx:
                    idx.append(app2idx[int(a)])
                    sc.append(float(s))
                    src.append("popularity-backfill")
        rows = self._rows(idx, sc, model)
        for r, s in zip(rows, src, strict=True):
            r["source"] = s
        return {"user_id": user_id, "mode": f"precomputed:{model}", "run_id": self.run_id, "items": rows}

    def for_new_user(self, tags: list[str]) -> dict:
        norm = [t.strip().lower().replace(" ", "_").replace("-", "_") for t in tags]
        cols = [self.tag_vocab[t] for t in norm if t in self.tag_vocab]
        if not cols:
            ids, sc = zip(*self.popular(), strict=True)
            return {"mode": "fallback:popularity (no known tags)", "items": self._rows(list(ids), list(sc), "popularity")}
        q = np.zeros(self.x_tag.shape[1], np.float32)
        q[cols] = self.tag_idf[cols]
        q /= np.linalg.norm(q)
        content = np.asarray(self.x_tag @ q).ravel()
        # light popularity prior so niche zero-review items do not dominate equally-tagged hits
        score = content * (1 + 0.1 * np.log1p(self.pop) / max(1.0, np.log1p(self.pop.max())))
        top = np.argsort(-score)[: self.k]
        top = [int(i) for i in top if score[i] > 0]
        unknown = [t for t, n in zip(tags, norm, strict=True) if n not in self.tag_vocab]
        return {"mode": "cold-start:tags", "unknown_tags": unknown,
                "items": self._rows(top, [float(score[i]) for i in top], "cb-tags")}


def pretty(res: dict) -> str:
    lines = [f"# {res.get('mode')}" + (f"  (run {res['run_id']})" if "run_id" in res else "")]
    if res.get("unknown_tags"):
        lines.append(f"  unknown tags ignored: {res['unknown_tags']}")
    for r in res["items"]:
        lines.append(f"{r['rank']:>3}. {r['title'][:48]:<48} app={r['app_id']:<8} {r['rating'] or '':<24} "
                     f"[{', '.join(r['tags'])}]" + (f"  <{r['source']}>" if "backfill" in r["source"] else ""))
    return "\n".join(lines)


def cache_dir(run_id: str) -> Path:
    return CACHE / run_id
