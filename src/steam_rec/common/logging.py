from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager

LOG = logging.getLogger("steam_rec")


def setup_logging(level: str = "INFO") -> None:
    if not LOG.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s", "%H:%M:%S"))
        LOG.addHandler(h)
    LOG.setLevel(level)


def peak_rss_mb() -> float:
    import resource

    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


@contextmanager
def phase(name: str, **ctx):
    """Log a phase with elapsed time; the yielded dict collects metrics (rows_in/out, ...)."""
    metrics: dict = {}
    LOG.info("▶ %s %s", name, json.dumps(ctx, default=str) if ctx else "")
    t0 = time.time()
    try:
        yield metrics
    except Exception:
        LOG.exception("✖ %s failed after %.1fs", name, time.time() - t0)
        raise
    metrics["elapsed_s"] = round(time.time() - t0, 1)
    metrics["driver_peak_rss_mb"] = peak_rss_mb()
    LOG.info("✔ %s %s", name, json.dumps(metrics, default=str))
