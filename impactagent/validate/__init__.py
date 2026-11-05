"""Compare our per-player metrics with a ground-truth JSON (data/validation/*.json).

Truth format: {"demo": path, "map": str, "rounds": int,
               "players": {name: {metric: value | null, ..., "steam_id"?: str, "aliases"?: [str]}}}.
Ratios are 0-1; null / absent metrics are skipped. Players are matched by steam_id, else by
name or one of its aliases.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from impactagent.metrics.registry import by_id, check_registry, ids_with_status

# Metrics that must match exactly (counts). Everything else is compared as a ratio.
COUNT_METRICS = {
    "kills", "deaths", "assists", "damage", "rounds_survived",
    "multi1k", "multi2k", "multi3k", "multi4k", "multi5k",
    "flash_thrown", "smoke_thrown", "he_thrown", "molotov_thrown",
    "enemies_flashed", "friends_flashed", "flash_assists", "flashes_leading_to_kill",
    "he_damage_enemies", "molotov_damage_enemies", "shots_fired",
    "trade_kill_opportunities", "trade_kill_attempts", "trade_kills_succeed",
    "traded_death_opportunities", "traded_death_attempts", "traded_deaths_succeed",
}
RATIO_REL_TOL = 0.03  # ~3% target from AGENTS.md
# Truth values are copied from a UI that rounds; allow half of the last shown digit
# (+ epsilon: 0.125 shown as 0.13 is exactly 0.005 off).
ROUNDING_ABS_TOL = 0.005 + 1e-9


def _is_nan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _status(metric: str, ours, theirs, implemented: bool = True) -> str:
    if not implemented:
        return "missing"
    if _is_nan(ours):  # undefined for us (e.g. 0/0); Leetify shows 0 there
        return "ok" if float(theirs) == 0 else "OFF"
    if metric in COUNT_METRICS:
        return "ok" if round(float(ours)) == round(float(theirs)) else "OFF"
    diff = abs(float(ours) - float(theirs))
    tol = max(RATIO_REL_TOL * abs(float(theirs)), ROUNDING_ABS_TOL)
    # integer-displayed values (ADR, $, ms) are rounded to whole units
    if float(theirs).is_integer() and abs(float(theirs)) >= 10:
        tol = max(tol, 0.5)
    return "ok" if diff <= tol else "OFF"


def match_players(ours: pd.DataFrame, truth_players: dict) -> dict[str, str]:
    """truth name -> our steam_id.

    Order: steam_id, then the truth name and its "aliases" (in-game names seen in the demo),
    exact first, then case-insensitive. A demo player is never matched twice.
    """
    by_name = {str(n): sid for sid, n in ours["name"].items()}
    by_name_ci = {str(n).casefold(): sid for sid, n in ours["name"].items()}
    out: dict[str, str] = {}
    for name, vals in truth_players.items():
        sid = str(vals.get("steam_id") or "")
        if sid and sid in ours.index:
            out[name] = sid
    used = set(out.values())
    for name, vals in truth_players.items():
        if name in out:
            continue
        candidates = [name, *(vals.get("aliases") or [])]
        hit = next((by_name[c] for c in candidates if c in by_name and by_name[c] not in used), None)
        if hit is None:
            hit = next((by_name_ci[c.casefold()] for c in candidates
                        if c.casefold() in by_name_ci and by_name_ci[c.casefold()] not in used), None)
        if hit is not None:
            out[name] = hit
            used.add(hit)
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
            implemented = metric in ours.columns
            ours_v = ours.at[sid, metric] if implemented else float("nan")
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
                    "status": _status(metric, ours_v, theirs, implemented),
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


KNOWN_EXCEPTIONS_PATH = Path(__file__).with_name("known_exceptions.yaml")


@lru_cache(maxsize=1)
def known_exceptions(path: str | Path = KNOWN_EXCEPTIONS_PATH) -> dict[tuple[str, str, str], str]:
    """(pair, player, metric) -> reason. One entry per cell whose cause is not known yet."""
    entries = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    out = {}
    for e in entries:
        missing = [f for f in ("pair", "player", "metric", "reason") if not e.get(f)]
        if missing:
            raise ValueError(f"known_exceptions.yaml: entry {e!r} misses {missing}")
        out[(str(e["pair"]), str(e["player"]), str(e["metric"]))] = str(e["reason"])
    return out


def apply_known_exceptions(df: pd.DataFrame, pair: str | None) -> tuple[pd.DataFrame, list[str]]:
    """OFF cells listed for this pair become `known` (not gating). Returns (df, stale entries
    that match again and can be removed)."""
    if pair is None or df.empty:
        return df, []
    exc = {(pl, m): r for (pa, pl, m), r in known_exceptions().items() if pa == pair}
    if not exc:
        return df, []
    df = df.copy()
    keys = list(zip(df["player"], df["metric"]))
    hit = pd.Series([k in exc for k in keys], index=df.index)
    stale = [f"{pl} {m}" for (pl, m) in exc if ((df["player"] == pl) & (df["metric"] == m) & (df["status"] == "ok")).any()]
    df.loc[hit & (df["status"] == "OFF"), "status"] = "known"
    return df, stale


# Per-round event kinds that gate validate-all.
GATING_EVENTS = {"opening", "clutch"}
# Reported but not gating: registry status `calibrating` (definition still a hypothesis).
CALIBRATING_METRICS = ids_with_status("calibrating")


def compare_events(p, ours: pd.DataFrame, truth: dict) -> pd.DataFrame:
    """Per-round lists in the truth file: opening_duels and clutches."""
    from impactagent.metrics.compute import build_clutches

    mapping = match_players(ours, truth["players"])
    name_of = {sid: n for n, sid in mapping.items()}
    rows = []
    if truth.get("opening_duels"):
        k = p.kills
        if "post_match" in k:
            k = k[~k["post_match"]]
        first = k[~k["is_team_kill"] & ~k["is_suicide"]].sort_values("tick").groupby("round_no").head(1)
        first = first.set_index("round_no")
        for od in truth["opening_duels"]:
            r = od["round"]
            exp = f"{od['attacker']} -> {od['victim']} ({od.get('attacker_side')})"
            if r in first.index:
                f0 = first.loc[r]
                got = f"{name_of.get(f0['attacker_id'], f0['attacker_id'])} -> {name_of.get(f0['victim_id'], f0['victim_id'])} ({f0['attacker_side']})"
            else:
                got = "-"
            rows.append({"kind": "opening", "round": r, "leetify": exp, "ours": got, "status": "ok" if exp == got else "OFF"})
    if truth.get("clutches") is not None:
        cl = build_clutches(p)
        cl = cl.assign(player=cl["steam_id"].map(name_of))
        ours_c = {(c.player, c.round_no): f"vs{c.vs_n} k{c.kills} {c.outcome}" for c in cl.itertuples()}
        exp_c = {(c["player"], c["round"]): f"vs{c['vs']} k{c['kills']} {c['outcome']}" for c in truth["clutches"]}
        for key in sorted(set(ours_c) | set(exp_c), key=lambda x: (x[1], str(x[0]))):
            e, o = exp_c.get(key, "-"), ours_c.get(key, "-")
            rows.append({"kind": "clutch", "round": key[1], "player": key[0], "leetify": e, "ours": o,
                         "status": "ok" if e == o else "OFF"})
    return pd.DataFrame(rows, columns=["kind", "round", "player", "leetify", "ours", "status"])


def _run(demo: str | Path, truth: dict, metrics: list[str] | None = None, pair: str | None = None):
    """-> (problems, metric df without unimplemented rows, unimplemented names, events df).
    `pair` (truth file stem) applies known_exceptions.yaml."""
    from impactagent.metrics.compute import compute_match_metrics
    from impactagent.parse.demo import parse_demo

    p = parse_demo(demo)
    ours = compute_match_metrics(p)
    problems = check_same_match(p, ours, truth)
    df = compare(ours, truth, metrics)
    df["group"] = df["metric"].map(lambda m: "calibrating" if m in CALIBRATING_METRICS else "core")
    df, stale = apply_known_exceptions(df, pair)
    _run.stale = stale
    not_impl = sorted(df.loc[df["status"] == "missing", "metric"].unique())
    events = compare_events(p, ours, truth) if not metrics else pd.DataFrame()
    _run.last_columns = set(ours.columns)  # for the registry check in validate_all
    return problems, df[df["status"] != "missing"], not_impl, events


def _score(df: pd.DataFrame) -> str:
    """ok / cells, known exceptions left out of the denominator."""
    return f"{int((df['status'] == 'ok').sum())}/{int((df['status'] != 'known').sum())}"


def _print_df(df: pd.DataFrame) -> None:
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


def validate_all(truth_dir: str | Path = "data/validation", metrics: list[str] | None = None) -> int:
    """Validate every truth JSON whose "demo" exists. Exit 1 only if a core metric or a
    per-round event is off; calibrating metrics are reported, not gating."""
    failed = False
    columns: set[str] | None = None
    tested_ok: set[str] = set()
    for path in sorted(Path(truth_dir).glob("*.json")):
        truth = json.loads(path.read_text(encoding="utf-8"))
        demo = Path(truth.get("demo") or "")
        if not demo.is_file():
            print(f"{path.name:<28} SKIP (demo not found: {demo})")
            continue
        problems, df, _, ev = _run(demo, truth, metrics, pair=path.stem)
        if problems:
            print(f"{path.name:<28} SKIP (different match: {'; '.join(problems)[:120]})")
            continue
        core, cal = df[df["group"] == "core"], df[df["group"] == "calibrating"]
        n_known = int((core["status"] == "known").sum())
        line = f"{path.name:<28} core {_score(core)} ok" + (f" (+{n_known} known exceptions)" if n_known else "")
        for kind in ("opening", "clutch"):
            sub = ev[ev["kind"] == kind] if not ev.empty else ev
            if len(sub):
                line += f" | {kind} {_score(sub)}" + ("" if kind in GATING_EVENTS else " (not gating)")
        if len(cal):
            line += f" | calibrating {_score(cal)} (not gating)"
        print(line)
        off = core[~core["status"].isin(["ok", "known"])]
        for row in core[core["status"] == "known"].itertuples():
            print(f"   known: {row.player} {row.metric} ours {row.ours:.3f} vs {row.leetify:.3f} - {known_exceptions()[(path.stem, row.player, row.metric)]}")
        for s in _run.stale:
            print(f"   STALE known exception (matches now, remove it): {s}")
        ev_off = ev[ev["status"] != "ok"] if not ev.empty else ev
        if not off.empty:
            _print_df(off.drop(columns="group"))
        if not ev_off.empty:
            _print_df(ev_off.assign(gating=ev_off["kind"].isin(GATING_EVENTS)))
        failed |= (not off.empty) or bool(len(ev_off) and ev_off["kind"].isin(GATING_EVENTS).any())
        columns = _run.last_columns
        tested_ok |= set(core.loc[core["status"] == "ok", "metric"])

    # Registry: well-formed, every id is computed, and which exact ids no truth file checks.
    reg = by_id()
    problems = check_registry(columns)
    print(f"registry.yaml                {len(reg)} metrics "
          f"({len(ids_with_status('exact'))} exact, {len(ids_with_status('calibrating'))} calibrating)"
          + (" | OK" if not problems else f" | {len(problems)} PROBLEMS"))
    for msg in problems:
        print("   -", msg)
    unchecked = sorted(m for m in ids_with_status("exact") if m not in tested_ok)
    if unchecked:
        print(f"   exact but not a truth-file metric (checked indirectly: per-round events / as a numerator): {', '.join(unchecked)}")
    missing = sorted(m for m in tested_ok if m not in reg)
    if missing:
        print(f"   validated but not in registry: {', '.join(missing)}")
    failed |= bool(problems)
    return 1 if failed else 0


def validate(demo: str | Path, truth_path: str | Path, metrics: list[str] | None = None,
             only_diff: bool = False, force: bool = False) -> int:
    truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))
    problems, df, not_impl, ev = _run(demo, truth, metrics, pair=Path(truth_path).stem)
    if problems:
        print("Demo and truth file look like DIFFERENT matches:")
        for msg in problems:
            print("  -", msg)
        if not force:
            print("Aborting (use --force to compare anyway).")
            return 2

    if df.empty:
        print("Nothing to compare.")
        return 1
    if not_impl:
        print(f"Not implemented yet (skipped): {', '.join(not_impl)}\n")
    shown = df[df["status"] != "ok"] if only_diff else df
    _print_df(shown)
    if not ev.empty:
        print("\nPer-round events:")
        _print_df(ev[ev["status"] != "ok"] if only_diff else ev)

    summary = (
        df.assign(ok=df["status"] == "ok")
        .groupby(["group", "metric"])
        .agg(ok=("ok", "sum"), n=("ok", "size"),
             mean_abs_pct=("pct_diff", lambda s: s.replace([float("inf")], float("nan")).abs().mean()))
        .sort_values(["group", "ok", "metric"])
    )
    print("\nPer metric (ok / n players):")
    with pd.option_context("display.max_rows", None):
        print(summary.to_string(float_format=lambda v: f"{v:.1%}"))
    core = df[df["group"] == "core"]
    ev_ok = ev.empty or bool((ev[ev["kind"].isin(GATING_EVENTS)]["status"] == "ok").all())
    print(f"\nTotal: core {_score(core)} ok, calibrating {_score(df[df['group'] == 'calibrating'])}"
          f"{', events ' + _score(ev) if not ev.empty else ''}, {len(not_impl)} metrics not implemented")
    return 0 if core["status"].isin(["ok", "known"]).all() and ev_ok else 1
