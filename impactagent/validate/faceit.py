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


class PlayerMatchError(ValueError):
    """Some FACEIT players could not be matched to a demo player."""


def match_players(truth_path: str | Path, p, tables=None) -> dict[str, str]:
    """FACEIT nickname -> steam_id for every player in the truth tables.

    1. optional truth key "aliases": {"<in-game name>": "<FACEIT name>"};
    2. exact, then case-insensitive name;
    3. elimination: inside one team (FACEIT table order <-> demo team `a`/`b` by the
       matched players), one name left on each side -> matched (printed).
    Raises PlayerMatchError listing the names still unmatched (never skips silently).
    """
    raw = json.loads(Path(truth_path).read_text(encoding="utf-8"))
    tables = tables or load_tables(truth_path)
    exact, ci = _name_map(p)
    alias = {str(fn): str(gn) for gn, fn in (raw.get("aliases") or {}).items()}
    team_of_sid = dict(zip(p.players["steam_id"], p.players["team"]))

    # FACEIT team index of each name (first tab|side that lists it).
    fteam: dict[str, int] = {}
    for teams in tables.values():
        for ti, team in enumerate(teams):
            for name in team:
                fteam.setdefault(name, ti)

    sid_of: dict[str, str] = {}
    for name in sorted(fteam):
        game = alias.get(name, name)
        sid = exact.get(game) or ci.get(game.casefold())
        if sid is not None:
            sid_of[name] = sid

    used = set(sid_of.values())
    for ti in sorted(set(fteam.values())):
        names = [n for n, t in fteam.items() if t == ti]
        left = [n for n in names if n not in sid_of]
        votes = pd.Series([team_of_sid.get(sid_of[n]) for n in names if n in sid_of]).value_counts()
        if not left or votes.empty:
            continue
        dteam = votes.index[0]
        free = [s for s, t in team_of_sid.items() if t == dteam and s not in used]
        if len(left) == 1 and len(free) == 1:
            sid_of[left[0]] = free[0]
            used.add(free[0])
            game = p.players.set_index("steam_id").at[free[0], "name"]
            print(f"matched by elimination: FACEIT {left[0]!r} <-> demo {game!r} ({free[0]})")

    missing = sorted(n for n in fteam if n not in sid_of)
    if missing:
        raise PlayerMatchError(
            "FACEIT players not matched to a demo player: " + ", ".join(missing)
            + ' (add "aliases": {"<in-game name>": "<FACEIT name>"} to the truth JSON)'
        )
    return sid_of


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
    try:
        sid_of = match_players(truth_path, p, tables)
    except PlayerMatchError as exc:
        print("FAIL:", exc)
        return 1

    pr = p.player_rounds_side
    played = {
        "All": pr.groupby("steam_id")["round_no"].nunique(),
        "CT": pr[pr["side"] == "CT"].groupby("steam_id")["round_no"].nunique(),
        "T": pr[pr["side"] == "T"].groupby("steam_id")["round_no"].nunique(),
    }

    # Every player name across all tab|side tables (a player appears in all 3 scopes).
    all_names = sorted({n for teams in tables.values() for team in teams for n in team})

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
