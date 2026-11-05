"""CLI report for `python -m impactagent impact DEMO` (impact-spec §3 / §5).

Builds rating_events for one demo, checks the invariants, writes Parquet, prints Impact per
player (% per round; the ×100 is `credit.PCT`) and, with a FACEIT scoreboard JSON, compares
it with FACEIT Swing. Report only: Impact is not expected to equal Swing (different models).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from impactagent.ratings.credit import (
    CATEGORIES,
    PCT,
    build_rating_events,
    check_invariants,
    impact_metrics,
    load_config,
    player_round_ratings,
)

_SHORT = {"opening_duel": "open", "mid_round_kd": "mid", "clutch": "clutch", "afterplant": "aftpl",
          "retake": "retake", "damage_assist": "dmg_a", "flash_assist": "fl_a", "traded": "traded",
          "enemy_saving": "save", "time": "time"}
_SCOPES = (("impact", "swing", "All"), ("impact_t", "swing_t", "T"), ("impact_ct", "swing_ct", "CT"))


def _pct_str(s) -> float:
    return float(str(s).replace("%", "").replace("+", "").replace(",", ""))


def _faceit_swing(truth_path, p) -> pd.DataFrame:
    """FACEIT Swing per steam_id: team (1/2 = table order), swing, swing_t, swing_ct."""
    from impactagent.validate.faceit import _name_map, load_tables

    tables = load_tables(truth_path)
    exact, ci = _name_map(p)
    rows: dict[str, dict] = {}
    for side, col in (("All", "swing"), ("T", "swing_t"), ("CT", "swing_ct")):
        for ti, team in enumerate(tables.get(("General", side), []), start=1):
            for name, vals in team.items():
                sid = exact.get(name) or ci.get(name.casefold())
                if sid is not None:
                    rows.setdefault(sid, {"team": ti})[col] = _pct_str(vals["Swing"])
    return pd.DataFrame.from_dict(rows, orient="index")


def _corr(a: pd.Series, b: pd.Series) -> tuple[float, float]:
    m = a.notna() & b.notna()
    a, b = a[m], b[m]
    if len(a) < 3:
        return float("nan"), float("nan")
    return float(np.corrcoef(a, b)[0, 1]), float(np.corrcoef(a.rank(), b.rank())[0, 1])


def _print_faceit(tab: pd.DataFrame) -> None:
    print(f"\n  {'player':<14}{'team':>5}{'rds':>5} | {'ours All':>9}{'T':>8}{'CT':>8} | "
          f"{'FACEIT All':>11}{'T':>8}{'CT':>8} | {'diff All':>9}")
    for _, r in tab.iterrows():
        team = int(r["team"]) if pd.notna(r["team"]) else "-"
        print(f"  {r['name']:<14}{team:>5}{int(r['rounds']):>5} | "
              f"{r['impact']:>+9.2f}{r['impact_t']:>+8.2f}{r['impact_ct']:>+8.2f} | "
              f"{r['swing']:>+11.2f}{r['swing_t']:>+8.2f}{r['swing_ct']:>+8.2f} | "
              f"{r['impact'] - r['swing']:>+9.2f}")
    print("\n  team sums of per-player per-round values (Σ over the team)")
    for col_o, col_f, lab in _SCOPES:
        parts = [f"team {int(ti)} ours {g[col_o].sum():+7.2f} FACEIT {g[col_f].sum():+7.2f}"
                 for ti, g in tab.groupby("team")]
        print(f"    {lab:<4}" + "  |  ".join(parts))
    print("\n  agreement (all players)")
    for col_o, col_f, lab in _SCOPES:
        r_, rho = _corr(tab[col_o], tab[col_f])
        mae = float((tab[col_o] - tab[col_f]).abs().mean())
        print(f"    {lab:<4} Pearson r {r_:+.3f}  Spearman rho {rho:+.3f}  MAE {mae:.2f} pp")
    for ti, g in tab.groupby("team"):
        _, rho = _corr(g["impact"], g["swing"])
        ours = ", ".join(g.sort_values("impact", ascending=False)["name"])
        theirs = ", ".join(g.sort_values("swing", ascending=False)["name"])
        print(f"    team {int(ti)} order (All), Spearman rho {rho:+.3f}\n      ours  : {ours}\n      FACEIT: {theirs}")


def _print_breakdown(ev: pd.DataFrame, tab: pd.DataFrame, played: pd.Series, n_rounds: int) -> None:
    e = ev[ev["steam_id"].notna()].copy()
    e["steam_id"] = e["steam_id"].astype(object)
    cats = [c for c in CATEGORIES if c != "disconnect" and (c != "time" or (e["category"] == "time").any())]
    b = (e.pivot_table(index="steam_id", columns="category", values="delta", aggfunc="sum")
         .reindex(columns=cats).fillna(0.0))
    b = b.div(played.reindex(b.index), axis=0) * PCT
    print("\n  breakdown (% per round played; row sum = All)")
    print(f"  {'player':<14}" + "".join(f"{_SHORT[c]:>8}" for c in cats) + f"{'sum':>8}")
    for sid, r in tab.iterrows():
        if sid in b.index:
            row = b.loc[sid]
            print(f"  {r['name']:<14}" + "".join(f"{row[c]:>+8.2f}" for c in cats) + f"{row.sum():>+8.2f}")
    nn = ev[ev["steam_id"].isna() & ~ev["is_bot"]]
    for side in ("T", "CT"):
        s = nn[nn["side"] == side].groupby("category")["delta"].sum() / n_rounds * PCT
        items = ", ".join(f"{k} {v:+.2f}" for k, v in s.items()) or "none"
        print(f"  no-player rows, {side} side (% per match round): {items}")


def run_impact(demo, out_dir=None, faceit=None, breakdown: bool = False, time_credit: str | None = None) -> int:
    """exit 0, or 1 if an invariant fails. time_credit overrides credit.yaml `time_credit`."""
    from impactagent.parse.demo import parse_demo

    p = parse_demo(demo)
    cfg = load_config()
    if time_credit:
        cfg["time_credit"] = time_credit
    ev, rounds = build_rating_events(p, cfg=cfg)
    probs = check_invariants(ev, rounds)
    prr = player_round_ratings(ev, p)
    im = impact_metrics(p, ev)

    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        ev.to_parquet(out / "rating_events.parquet", index=False)
        prr.to_parquet(out / "player_round_ratings.parquet", index=False)

    names = p.players.set_index("steam_id")["name"].astype(str)
    played = p.player_rounds_side.groupby("steam_id")["round_no"].nunique()
    tab = im.join(names).assign(rounds=played)
    n_null = int(ev["steam_id"].isna().sum())
    print(f"impact: {Path(demo).name}  map={p.map_name} rounds={len(p.rounds)} rows={len(ev)} "
          f"time_credit={cfg['time_credit']} "
          f"(steam_id null: {n_null} time / disconnect / bot)")
    bots = int(ev["is_bot"].sum())
    if bots:
        print(f"  WARN: {bots} bot rows (steam_id null)")
    status = "OK" if not probs else f"{len(probs)} FAILED"
    print(f"  invariants over {len(rounds)} rounds (a) T = t_won - wp_start, (b) T + CT = 0, "
          f"(c) players + time/disconnect = (a), per-state = dWP: {status}")
    for pr_ in probs[:20]:
        print("   ", pr_)
    if out_dir is not None:
        print(f"  -> {Path(out_dir) / 'rating_events.parquet'}, player_round_ratings.parquet")

    if faceit:
        tab = tab.join(_faceit_swing(faceit, p)).sort_values(["team", "impact"], ascending=[True, False])
        _print_faceit(tab)
    else:
        tab = tab.sort_values("impact", ascending=False)
        print(f"\n  {'player':<16}{'rds':>5}{'All':>9}{'T':>8}{'CT':>8}   (% per round)")
        for _, r in tab.iterrows():
            print(f"  {r['name']:<16}{int(r['rounds']):>5}{r['impact']:>+9.2f}"
                  f"{r['impact_t']:>+8.2f}{r['impact_ct']:>+8.2f}")
    if breakdown:
        _print_breakdown(ev, tab, played, len(p.rounds))
    return 1 if probs else 0
