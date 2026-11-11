"""Build reports/benchmark.md from run artifacts in the lake (stage timings + validation/test metrics)."""

from __future__ import annotations

import json

from steam_rec.storage import paths
from steam_rec.storage.store import Store

STAGES = ["silver", "gold", "train", "evaluate", "recommend"]
MODELS = ["popularity", "cb", "als"]


def _j(store: Store, key: str):
    return json.loads(store.get_text(key)) if store.exists(key) else None


def run_summary(store: Store, run_id: str) -> dict:
    a = lambda *p: paths.artifacts(run_id, *p)
    stages = {s: _j(store, a("stages", f"{s}.json")) for s in STAGES}
    return {"run_id": run_id, "run": _j(store, a("run.json")) or {}, "stages": stages,
            "test": _j(store, a("metrics", "test.json")), "val": _j(store, a("metrics", "validation.json"))}


def render(runs: list[dict], k: int = 20) -> str:
    out = ["# Benchmark — Steam Recommendation MVP", "",
           "Spark `local[*]` trên **một máy** (đa nhân, không phải cluster). Thời gian là wall-clock của từng stage.", ""]
    out += ["## Quy mô và thời gian", "",
            "| run | nơi chạy | scale | users | items | train interactions | eval users | "
            + " | ".join(f"{s} (s)" for s in STAGES) + " |",
            "|" + "---|" * (7 + len(STAGES))]
    for r in runs:
        st = r["stages"]
        g = (st.get("gold") or {}).get("metrics", {})
        sp, ev = g.get("split", {}), g.get("eval", {})
        out.append(f"| `{r['run_id']}` | {r['run'].get('execution', '?')} | {r['run'].get('scale', '?')} | "
                   f"{sp.get('users', '?'):,} | {sp.get('items', '?'):,} | {sp.get('n_train', '?'):,} | "
                   f"{ev.get('eval_users', '?'):,} | "
                   + " | ".join(str((st.get(s) or {}).get("elapsed_s", "—")) for s in STAGES) + " |")
    for r in runs:
        if not r["test"]:
            continue
        sel = r["test"].get("_selection", {})
        out += ["", f"## Test metrics — `{r['run_id']}` ({r['run'].get('scale')})", "",
                (f"Cấu hình chọn trên validation ({sel.get('primary_metric')}): ALS `{sel.get('als')}`, "
                 f"CB `{sel.get('cb')}`. Test chỉ chạy **một lần**."), "",
                "| model | Recall@10 | NDCG@10 | Recall@20 | NDCG@20 | catalog cov@20 | eligible users@20 |",
                "|---|---|---|---|---|---|---|"]
        for m in MODELS:
            t = r["test"][m]
            out.append(f"| {m} | {t['recall@10']:.4f} | {t['ndcg@10']:.4f} | {t['recall@20']:.4f} | "
                       f"{t['ndcg@20']:.4f} | {t['catalog_coverage@20']:.3f} | {t['eligible_user_coverage@20']:.3f} |")
        if r["val"]:
            out += ["", "<details><summary>Validation grid</summary>", "",
                    "| model | params | NDCG@20 | Recall@20 |", "|---|---|---|---|"]
            for m in MODELS:
                for row in r["val"].get(m, []):
                    out.append(f"| {m} | `{row['params']}` | {row['val'][f'ndcg@{k}']:.4f} | "
                               f"{row['val'][f'recall@{k}']:.4f} |")
            out += ["", "</details>"]
    return "\n".join(out) + "\n"
