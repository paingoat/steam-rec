"""Stages: train (tune on validation) -> evaluate (test, once, selected configs) -> recommend (top-K export)."""

from __future__ import annotations

import itertools
import json
import os

from pyspark.ml.recommendation import ALSModel
from pyspark.sql import functions as F

from steam_rec.common.logging import LOG, phase
from steam_rec.evaluation.metrics import spark_metrics
from steam_rec.models import als as als_m
from steam_rec.models import cb_tfidf
from steam_rec.models.popularity import fit_popularity
from steam_rec.models.scoring import topk, user_inputs
from steam_rec.pipelines.runner import Ctx, StageIncomplete
from steam_rec.storage.arrays import get_npy, get_npz, put_npy, put_npz

PRIMARY = "ndcg@{k}"
TOPK_EXPORT = 20


def _n_items(ctx: Ctx) -> int:
    return ctx.read(ctx.gold("id_map_items")).count()


def _kmax(ctx: Ctx) -> int:
    return max(ctx.cfg.eval.k_values)


def _eval(ctx: Ctx, inputs, kind, state, target_col: str, n_items: int) -> dict:
    recs = topk(inputs, kind, state, _kmax(ctx))
    tgt = ctx.read(ctx.gold("eval_targets")).select("user_idx", target_col)
    return spark_metrics(recs.join(tgt, "user_idx"), target_col, ctx.cfg.eval.k_values, n_items)


def _grid(g: dict) -> list[dict]:
    keys = list(g)
    return [dict(zip(keys, vals, strict=True)) for vals in itertools.product(*[g[k] for k in keys])]


def _trial_key(params: dict) -> str:
    return "_".join(f"{k}{params[k]:g}" if isinstance(params[k], float) else f"{k}{params[k]}" for k in sorted(params))


def run_train(ctx: Ctx) -> dict:
    """Resumable: every sub-result is persisted under models/trials/ as soon as it exists, so a timeout or VM reset
    only re-runs what is missing. STEAM_REC_MAX_ALS_FITS caps new ALS fits per invocation (keeps each
    `colab exec` well under its timeout); the stage is only marked done once every grid point is evaluated."""
    n_items, k = _n_items(ctx), _kmax(ctx)
    primary = PRIMARY.format(k=k)
    trial = lambda name: ctx.art("models", "trials", f"{name}.json")
    have = lambda name: ctx.store.exists(trial(name))
    targets = ctx.read(ctx.gold("eval_targets"))
    inp = user_inputs(ctx, targets, "val").checkpoint(eager=True)

    if not have("popularity"):
        with phase("train.popularity"):
            pop = fit_popularity(ctx, n_items)
            put_npy(ctx.store, ctx.art("models", "popularity.npy"), pop)
            ctx.put_json(trial("popularity"), [{"params": {}, "val": _eval(ctx, inp, "pop", pop, "val_item", n_items)}])

    if not have("cb"):
        with phase("train.cb"):
            cbp = ctx.cfg.model["cb"]
            feats = cb_tfidf.build_item_features(ctx, n_items)
            best, rows = None, []
            for params in _grid(cbp.get("grid", {"w_desc": [cbp["w_desc"]]})):
                w_desc = float(params.get("w_desc", cbp["w_desc"]))
                s = cb_tfidf.item_knn(cb_tfidf.combine(feats["X_tag"], feats["X_desc"], float(cbp["w_tag"]), w_desc),
                                      int(cbp["neighbors"]))
                met = _eval(ctx, inp, "cb", s, "val_item", n_items)
                rows.append({"params": {"w_tag": float(cbp["w_tag"]), "w_desc": w_desc,
                                        "neighbors": int(cbp["neighbors"])}, "val": met})
                LOG.info("cb w_desc=%s %s", w_desc, met)
                if best is None or met[primary] > best[0]:
                    best = (met[primary], s)
            put_npz(ctx.store, ctx.art("models", "cb_item_knn.npz"), best[1])
            put_npz(ctx.store, ctx.art("models", "cb_x_tag.npz"), feats["X_tag"])
            put_npy(ctx.store, ctx.art("models", "cb_tag_idf.npy"), feats["tag_idf"])
            ctx.store.put_text(ctx.art("models", "cb_tag_vocab.json"), json.dumps(feats["tag_vocab"]))
            ctx.put_json(trial("cb"), rows)

    grid = _grid(ctx.cfg.model["als"]["grid"])
    budget = int(os.environ.get("STEAM_REC_MAX_ALS_FITS", "1000"))
    for params in grid:
        key = f"als_{_trial_key(params)}"
        if have(key):
            continue
        if budget <= 0:
            done = sum(have(f"als_{_trial_key(p)}") for p in grid)
            raise StageIncomplete(f"ALS grid {done}/{len(grid)} evaluated; re-run the train stage to continue")
        budget -= 1
        with phase("train.als.fit", **params):
            model = als_m.fit_als(ctx, params)
        met = _eval(ctx, als_m.with_user_factors(inp, model), "als",
                    als_m.item_factors(model, n_items), "val_item", n_items)
        LOG.info("als %s %s", params, met)
        model.write().overwrite().save(ctx.uri(ctx.art("models", "als_trials", key)))
        ctx.put_json(trial(key), [{"params": params, "val": met, "model": key}])

    # finalize: pick best per family on validation
    results = {"popularity": ctx.get_json(trial("popularity")), "cb": ctx.get_json(trial("cb")),
               "als": [ctx.get_json(trial(f"als_{_trial_key(p)}"))[0] for p in grid]}
    best_als = max(results["als"], key=lambda r: r["val"][primary])
    best_cb = max(results["cb"], key=lambda r: r["val"][primary])
    model = ALSModel.load(ctx.uri(ctx.art("models", "als_trials", best_als["model"])))
    model.write().overwrite().save(ctx.uri(ctx.art("models", "als")))
    put_npy(ctx.store, ctx.art("models", "als_item_factors.npy"), als_m.item_factors(model, n_items))
    for r in results["als"]:  # non-selected trial models are scratch (~1 GB each at full scale)
        if r["model"] != best_als["model"]:
            ctx.store.delete_prefix(ctx.art("models", "als_trials", r["model"]))
    selection = {"primary_metric": primary, "als": best_als["params"], "cb": best_cb["params"]}
    ctx.put_json(ctx.art("models", "selection.json"), selection)
    ctx.put_json(ctx.art("metrics", "validation.json"), results)
    return {"selection": selection,
            "val_best": {m: max(r["val"][primary] for r in rs) for m, rs in results.items()}}


def run_evaluate(ctx: Ctx) -> dict:
    """Test split, evaluated exactly once with the configs selected on validation."""
    n_items = _n_items(ctx)
    targets = ctx.read(ctx.gold("eval_targets"))
    inp = user_inputs(ctx, targets, "test").checkpoint(eager=True)
    out = {}
    with phase("evaluate.test"):
        out["popularity"] = _eval(ctx, inp, "pop", get_npy(ctx.store, ctx.art("models", "popularity.npy")),
                                  "test_item", n_items)
        out["cb"] = _eval(ctx, inp, "cb", get_npz(ctx.store, ctx.art("models", "cb_item_knn.npz")),
                          "test_item", n_items)
        model = ALSModel.load(ctx.uri(ctx.art("models", "als")))
        out["als"] = _eval(ctx, als_m.with_user_factors(inp, model), "als",
                           get_npy(ctx.store, ctx.art("models", "als_item_factors.npy")), "test_item", n_items)
    out["_selection"] = ctx.get_json(ctx.art("models", "selection.json"))
    ctx.put_json(ctx.art("metrics", "test.json"), out)
    for m in ("popularity", "cb", "als"):
        LOG.info("TEST %-10s %s", m, out[m])
    return out


def run_recommend(ctx: Ctx) -> dict:
    """Precompute top-K (all history masked) for eval + demo users, for every model -> recommendations_topk."""
    users = (ctx.read(ctx.gold("eval_targets")).select("user_idx")
             .unionByName(ctx.read(ctx.gold("demo_users"))).distinct())
    inp = user_inputs(ctx, users, "all").checkpoint(eager=True)
    model = ALSModel.load(ctx.uri(ctx.art("models", "als")))
    parts = {
        "popularity": topk(inp, "pop", get_npy(ctx.store, ctx.art("models", "popularity.npy")), TOPK_EXPORT),
        "cb": topk(inp, "cb", get_npz(ctx.store, ctx.art("models", "cb_item_knn.npz")), TOPK_EXPORT),
        "als": topk(als_m.with_user_factors(inp, model), "als",
                    get_npy(ctx.store, ctx.art("models", "als_item_factors.npy")), TOPK_EXPORT),
    }
    umap = ctx.read(ctx.gold("id_map_users"))
    imap = F.broadcast(ctx.read(ctx.gold("id_map_items")))
    out = None
    for name, df in parts.items():
        ex = (df.select("user_idx", F.posexplode(F.arrays_zip("items", "scores")).alias("pos", "z"))
              .select("user_idx", (F.col("pos") + 1).alias("rank"), F.col("z.items").alias("item_idx"),
                      F.col("z.scores").alias("score"))
              .withColumn("model", F.lit(name)))
        out = ex if out is None else out.unionByName(ex)
    out = (out.join(umap, "user_idx").join(imap, "item_idx")
           .select("user_id", "app_id", "rank", "score", "model", F.lit(ctx.run_id).alias("run_id")))
    ctx.write(out.repartition(4), ctx.art("topk"))
    # demo side-cars: catalog subset + popularity fallback list
    cat = ctx.read(ctx.silver("game_catalog")).join(imap, "app_id").select(
        "item_idx", "app_id", "title", "rating", "positive_ratio", "price_final", "tags")
    ctx.write(cat.coalesce(1), ctx.art("catalog"))
    ctx.write(umap.join(users, "user_idx").coalesce(1), ctx.art("topk_users"))
    n = ctx.read(ctx.art("topk")).count()
    return {"rows": n, "users": users.count()}
