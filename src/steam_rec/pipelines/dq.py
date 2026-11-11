"""Tiny data-quality framework: each check -> {name, value, level, ok}. Any failed 'fail'-level check raises."""

from __future__ import annotations

from steam_rec.common.logging import LOG


class DQError(RuntimeError):
    pass


class DQ:
    def __init__(self) -> None:
        self.results: list[dict] = []

    def check(self, name: str, value, ok: bool, level: str = "fail") -> None:
        self.results.append({"name": name, "value": value, "level": level, "ok": bool(ok)})
        if not ok:
            (LOG.error if level == "fail" else LOG.warning)("DQ %s: %s = %s", level.upper(), name, value)

    def raise_if_failed(self) -> None:
        bad = [r for r in self.results if not r["ok"] and r["level"] == "fail"]
        if bad:
            raise DQError(f"data quality failed: {bad}")
