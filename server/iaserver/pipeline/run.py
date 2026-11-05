"""run_match(demo) -> MatchBundle: parse + state snapshot + wp_states + Impact + metrics.

Calls impactagent's public functions only (no metric logic here). The demo is decompressed
once; parse and the state snapshot read the same plain .dem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd

from impactagent.constants import MAX_DEMO_BYTES, PARSE_TIMEOUT_SECONDS
from impactagent.metrics.compute import match_tables
from impactagent.metrics.registry import load_registry
from impactagent.parse.demo import demo_file, parse_demo
from impactagent.parse.io import parsed_tables
from impactagent.ratings.credit import build_rating_events, check_invariants, player_round_ratings
from impactagent.ratings.wp_states import StateSnapshot, build_wp_states, read_state_snapshots, state_ticks_of

from iaserver.pipeline.versions import components, pipeline_version

METRIC_VALUE_COLUMNS = ["match_id", "steam_id", "metric_id", "scope", "value", "numerator", "denominator"]


class InvariantError(RuntimeError):
    """Impact invariants failed: a bug on our side (job fault `ours`)."""


@dataclass
class MatchBundle:
    source: Path
    sha256: str                    # sha256 of the plain .dem (= matches.dem_sha256)
    map_name: str
    tickrate: int
    client_build: int | None
    rounds_played: int
    events: dict[str, pd.DataFrame]
    snapshot: StateSnapshot
    derived: dict[str, pd.DataFrame]
    versions: dict
    pipeline_version: str
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    wp_stats: dict = field(default_factory=dict)


def metric_values_long(metrics: pd.DataFrame, match_id: str) -> pd.DataFrame:
    """Wide per-player metrics -> long metric_values (scope `all`). numerator / denominator
    are null until the metric functions return them (roadmap 3.1c)."""
    ids = [m["id"] for m in load_registry() if m["id"] in metrics.columns]
    long = (metrics[ids].reset_index().melt(id_vars="steam_id", var_name="metric_id", value_name="value"))
    long.insert(0, "match_id", match_id)
    long["scope"] = "all"
    long["value"] = pd.to_numeric(long["value"], errors="coerce").astype("float64")
    long["numerator"] = pd.Series(pd.NA, index=long.index, dtype="Float64")
    long["denominator"] = pd.Series(pd.NA, index=long.index, dtype="Float64")
    return long[METRIC_VALUE_COLUMNS]


def run_match(dem_path: str | Path, timeout: float | None = PARSE_TIMEOUT_SECONDS,
              max_bytes: int | None = MAX_DEMO_BYTES) -> MatchBundle:
    """Raises DemoTooLargeError / ParseTimeoutError (from parse) or InvariantError."""
    path = Path(dem_path)
    if not path.exists():
        raise FileNotFoundError(path)
    t: dict[str, float] = {}
    t0 = time.perf_counter()
    with demo_file(path, max_bytes) as (plain, _sha):
        t["decompress"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        p = parse_demo(plain, timeout=timeout, max_bytes=max_bytes)
        t["parse"] = time.perf_counter() - t1
        t1 = time.perf_counter()
        snap = read_state_snapshots(plain, state_ticks_of(p))
        t["snapshot"] = time.perf_counter() - t1
    p = replace(p, path=path)  # the temp .dem is gone; keep the original for messages

    t1 = time.perf_counter()
    states, wp_stats = build_wp_states(p, snapshot=snap)
    events, ev_rounds = build_rating_events(p, states)
    problems = check_invariants(events, ev_rounds)
    if problems:
        raise InvariantError(f"{path.name}: {len(problems)} invariant failures, e.g. {problems[:3]}")
    prr = player_round_ratings(events, p)
    t["wp_credit"] = time.perf_counter() - t1

    t1 = time.perf_counter()
    mt = match_tables(p, events)
    metrics = mt["metrics"]
    derived = {
        "wp_states": states,
        "rating_events": events,
        "player_round_ratings": prr,
        "player_rounds": mt["player_rounds"],
        "clutches": mt["clutches"],
        "metrics": metrics.reset_index(),
        "metric_values": metric_values_long(metrics, p.sha256),
    }
    t["metrics"] = time.perf_counter() - t1

    comps = components()
    return MatchBundle(
        source=path, sha256=p.sha256, map_name=p.map_name, tickrate=p.tickrate,
        client_build=p.client_build, rounds_played=len(p.rounds),
        events=parsed_tables(p), snapshot=snap, derived=derived,
        versions=comps, pipeline_version=pipeline_version(comps),
        timings=t, warnings=list(p.warnings) + list(wp_stats.get("timer_warns", [])), wp_stats=wp_stats,
    )
