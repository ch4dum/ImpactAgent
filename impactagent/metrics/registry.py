"""Load and check the metric registry (registry.yaml, data-model §4)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")

REQUIRED = ("id", "label", "category", "unit", "direction", "aggregation", "source", "scopes", "status")
CATEGORIES = {"rating", "general", "aim", "positioning", "utility"}
DIRECTIONS = {"higher_better", "lower_better", "neutral"}
AGGREGATIONS = {"ratio", "median", "sum", "mean"}
STATUSES = {"exact", "calibrating", "custom"}
SCOPES = {"all", "CT", "T"}


@lru_cache(maxsize=1)
def load_registry(path: str | Path = REGISTRY_PATH) -> tuple[dict, ...]:
    entries = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    return tuple(entries)


def by_id() -> dict[str, dict]:
    return {m["id"]: m for m in load_registry()}


def ids_with_status(status: str) -> set[str]:
    return {m["id"] for m in load_registry() if m.get("status") == status}


def check_registry(computed_columns: set[str] | None = None) -> list[str]:
    """Problems with the registry (empty list = fine)."""
    problems = []
    seen = set()
    for m in load_registry():
        mid = m.get("id", "?")
        if mid in seen:
            problems.append(f"{mid}: duplicate id")
        seen.add(mid)
        for f in REQUIRED:
            if f not in m:
                problems.append(f"{mid}: missing field {f}")
        if m.get("category") not in CATEGORIES:
            problems.append(f"{mid}: bad category {m.get('category')!r}")
        if m.get("direction") not in DIRECTIONS:
            problems.append(f"{mid}: bad direction {m.get('direction')!r}")
        if m.get("aggregation") not in AGGREGATIONS:
            problems.append(f"{mid}: bad aggregation {m.get('aggregation')!r}")
        if m.get("aggregation") == "ratio" and not (m.get("numerator") and m.get("denominator")):
            problems.append(f"{mid}: ratio needs numerator and denominator")
        if m.get("status") not in STATUSES:
            problems.append(f"{mid}: bad status {m.get('status')!r}")
        if not set(m.get("scopes") or []) <= SCOPES:
            problems.append(f"{mid}: bad scopes {m.get('scopes')!r}")
        if computed_columns is not None and mid not in computed_columns:
            problems.append(f"{mid}: not produced by compute_match_metrics")
    return problems
