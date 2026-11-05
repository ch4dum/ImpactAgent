"""Compare our metrics against a FACEIT scoreboard JSON (impact-spec §5).

Truth format (a FACEIT match-room grab):
  {"url": ..., "grabbed": ..., "<Tab>|<Side>": [[header, row, ...], [header, row, ...]]}
  - each "<Tab>|<Side>" is a list of 2 tables (one per team);
  - a table is a list of rows, row 0 = the header, values are strings ("19.95", "76.5%", "2,247").

Currently compares RWS (Advanced, scopes All / T / CT) and RP. The metric list is a small
data table (METRICS) so KAST / Entry / Trade / Clutch / MK can be added without restructuring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

TOL = 0.01  # exact within ±0.01 (impact-spec §5)

# Metric -> (tab, column, cast). Scopes (All / T / CT) are handled uniformly below.
METRICS = {
    "RWS": ("Advanced", "RWS", float),
    "RP": ("Advanced", "RP", int),
}


def load_tables(path: str | Path) -> dict[tuple[str, str], list[dict[str, dict[str, str]]]]:
    """{(tab, side): [ {player: {column: value_string}}, ... ]} — one dict per team."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[tuple[str, str], list[dict[str, dict[str, str]]]] = {}
    for key, teams in raw.items():
        if "|" not in key:
            continue
        tab, side = key.split("|", 1)
        out[(tab, side)] = [
            {row[0]: dict(zip(table[0][1:], row[1:])) for row in table[1:]}
            for table in teams
        ]
    return out


def _players(tables, tab: str, side: str) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for team in tables.get((tab, side), []):
        merged.update(team)
    return merged


def _name_map(p) -> tuple[dict[str, str], dict[str, str]]:
    """(exact, casefold) FACEIT nickname -> steam_id."""
    by_sid = {sid: str(n) for sid, n in p.players.set_index("steam_id")["name"].items()}
    exact = {n: sid for sid, n in by_sid.items()}
    ci = {n.casefold(): sid for sid, n in by_sid.items()}
    return exact, ci


def _our_value(ours: pd.DataFrame, played: dict[str, pd.Series], metric: str, side: str) -> pd.Series:
    if metric == "RWS":
        return {"All": ours["rws"], "CT": ours["rws_ct"], "T": ours["rws_t"]}[side]
    if metric == "RP":
        return played[side]
    raise KeyError(metric)


def run(demo: str | Path, truth_path: str | Path) -> int:
    from impactagent.metrics.compute import compute_match_metrics
    from impactagent.parse.demo import parse_demo

    p = parse_demo(demo)
    ours = compute_match_metrics(p)
    tables = load_tables(truth_path)
    exact, ci = _name_map(p)

    pr = p.player_rounds_side
    played = {
        "All": pr.groupby("steam_id")["round_no"].nunique(),
        "CT": pr[pr["side"] == "CT"].groupby("steam_id")["round_no"].nunique(),
        "T": pr[pr["side"] == "T"].groupby("steam_id")["round_no"].nunique(),
    }

    # Every player name across all tab|side tables (a player appears in all 3 scopes).
    all_names = sorted({n for teams in tables.values() for team in teams for n in team})
    sid_of: dict[str, str] = {}
    missing = []
    for name in all_names:
        if name in exact:
            sid_of[name] = exact[name]
        elif name.casefold() in ci:
            sid_of[name] = ci[name.casefold()]
        else:
            missing.append(name)
    if missing:
        print("FACEIT players not matched to a demo player:", ", ".join(missing))

    off = 0
    for metric, (tab, col, cast) in METRICS.items():
        rows = []
        for name in all_names:
            sid = sid_of.get(name)
            row: dict = {"player": name}
            for side in ("All", "T", "CT"):
                truth_val = _players(tables, tab, side).get(name, {}).get(col)
                row[f"{side}_faceit"] = cast(truth_val) if truth_val not in (None, "") else None
                row[f"{side}_ours"] = _our_value(ours, played, metric, side).get(sid) if sid else None
                if row[f"{side}_ours"] is not None and row[f"{side}_faceit"] is not None:
                    row[f"{side}_diff"] = round(row[f"{side}_ours"] - row[f"{side}_faceit"], 4)
                else:
                    row[f"{side}_diff"] = None
            rows.append(row)

        df = pd.DataFrame(rows)
        print(f"\n=== {metric} ({tab}) — ours / FACEIT / diff, per scope ===")
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

        for r in rows:
            for side in ("All", "T", "CT"):
                d = r[f"{side}_diff"]
                if d is not None and abs(d) > TOL + 1e-9:
                    off += 1

    print(f"\nCells off by more than ±{TOL}: {off}")
    return 1 if off else 0
