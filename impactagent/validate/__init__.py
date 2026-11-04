"""Compare our per-player metrics with a ground-truth JSON (data/validation/*.json).

Truth format: {"rounds": int, "players": {name: {metric: value, ..., "steam_id"?: str}}}.
Ratios are 0-1. Players are matched by steam_id when given, else by in-game name.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

# Metrics that must match exactly (counts). Everything else is compared as a ratio.
COUNT_METRICS = {
    "kills", "deaths", "assists", "damage", "rounds_survived",
    "multi1k", "multi2k", "multi3k", "multi4k", "multi5k",
    "flash_thrown", "smoke_thrown", "he_thrown", "molotov_thrown",
    "enemies_flashed", "friends_flashed", "flash_assists", "flashes_leading_to_kill",
    "he_damage_enemies", "molotov_damage_enemies", "shots_fired",
}
RATIO_REL_TOL = 0.03  # ~3% target from AGENTS.md
# Truth values are copied from a UI that rounds; allow half of the last shown digit.
ROUNDING_ABS_TOL = 0.005


def _is_nan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _status(metric: str, ours, theirs) -> str:
    if _is_nan(ours):
        return "missing"
    if metric in COUNT_METRICS:
        return "ok" if round(float(ours)) == round(float(theirs)) else "OFF"
    diff = abs(float(ours) - float(theirs))
    tol = max(RATIO_REL_TOL * abs(float(theirs)), ROUNDING_ABS_TOL)
    # integer-displayed values (ADR, $, ms) are rounded to whole units
    if float(theirs).is_integer() and abs(float(theirs)) >= 10:
        tol = max(tol, 0.5)
    return "ok" if diff <= tol else "OFF"


def match_players(ours: pd.DataFrame, truth_players: dict) -> dict[str, str]:
    """truth name -> our steam_id."""
    by_name = {str(n): sid for sid, n in ours["name"].items()}
    by_name_ci = {str(n).casefold(): sid for sid, n in ours["name"].items()}
    out = {}
    for name, vals in truth_players.items():
        sid = str(vals.get("steam_id") or "")
        if sid and sid in ours.index:
            out[name] = sid
        elif name in by_name:
            out[name] = by_name[name]
        elif name.casefold() in by_name_ci:
            out[name] = by_name_ci[name.casefold()]
    return out


def compare(ours: pd.DataFrame, truth: dict, metrics: list[str] | None = None) -> pd.DataFrame:
    mapping = match_players(ours, truth["players"])
    rows = []
    for name, sid in mapping.items():
        for metric, theirs in truth["players"][name].items():
            if metric == "steam_id" or (metrics and metric not in metrics):
                continue
            if _is_nan(theirs) or not isinstance(theirs, (int, float)):
                continue
            ours_v = ours.at[sid, metric] if metric in ours.columns else float("nan")
            ours_v = float("nan") if _is_nan(ours_v) else float(ours_v)
            diff = ours_v - float(theirs)
            pct = diff / float(theirs) if float(theirs) else (0.0 if diff == 0 else float("inf"))
            rows.append(
                {
                    "player": name,
                    "metric": metric,
                    "ours": ours_v,
                    "leetify": float(theirs),
                    "diff": diff,
                    "pct_diff": pct,
                    "status": _status(metric, ours_v, theirs),
                }
            )
    return pd.DataFrame(rows, columns=["player", "metric", "ours", "leetify", "diff", "pct_diff", "status"])


def check_same_match(p, ours: pd.DataFrame, truth: dict) -> list[str]:
    """Reasons the demo and truth file look like different matches (empty = looks fine)."""
    problems = []
    if truth.get("map") and truth["map"] != p.map_name:
        problems.append(f"map: demo={p.map_name} truth={truth['map']}")
    if truth.get("rounds") and int(truth["rounds"]) != len(p.rounds):
        problems.append(f"rounds: demo={len(p.rounds)} truth={truth['rounds']}")
    mapping = match_players(ours, truth["players"])
    missing = sorted(set(truth["players"]) - set(mapping))
    if missing:
        problems.append(f"{len(missing)}/{len(truth['players'])} truth players not in demo: {missing}")
    return problems


def validate(demo: str | Path, truth_path: str | Path, metrics: list[str] | None = None,
             only_diff: bool = False, force: bool = False) -> int:
    from impactagent.metrics.compute import compute_match_metrics
    from impactagent.parse.demo import parse_demo

    truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))
    p = parse_demo(demo)
    ours = compute_match_metrics(p)

    problems = check_same_match(p, ours, truth)
    if problems:
        print("Demo and truth file look like DIFFERENT matches:")
        for msg in problems:
            print("  -", msg)
        if not force:
            print("Aborting (use --force to compare anyway).")
            return 2

    df = compare(ours, truth, metrics)
    if df.empty:
        print("Nothing to compare.")
        return 1
    shown = df[df["status"] != "ok"] if only_diff else df
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(shown.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    summary = (
        df.assign(ok=df["status"] == "ok", missing=df["status"] == "missing")
        .groupby("metric")
        .agg(ok=("ok", "sum"), n=("ok", "size"), missing=("missing", "sum"),
             mean_abs_pct=("pct_diff", lambda s: s.replace([float("inf")], float("nan")).abs().mean()))
        .sort_values(["ok", "metric"])
    )
    print("\nPer metric (ok / n players):")
    with pd.option_context("display.max_rows", None):
        print(summary.to_string(float_format=lambda v: f"{v:.1%}"))
    n_ok = int((df["status"] == "ok").sum())
    print(f"\nTotal: {n_ok}/{len(df)} ok, {int((df['status'] == 'missing').sum())} not implemented")
    return 0 if n_ok == len(df) else 1
