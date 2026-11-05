"""Kill visibility report: how often each backend says the killer could see his victim.

A gun kill without wallbang / smoke should be "seen" ~100%; through-smoke kills should drop
once smokes block; wallbangs are mostly not seen. CLI: ``python -m impactagent visibility DEMO...``
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from impactagent.visibility import RaycastBackend, SpottedBackend, TickStates, check_pairs, load_mesh
from impactagent.visibility.smoke import SmokeIndex

FIRE_LOOKBACK_TICKS = 192  # 3 s: last weapon_fire of the killer before the kill
NON_HITSCAN = {"hegrenade", "flashbang", "smokegrenade", "decoy", "molotov", "incgrenade", "inferno",
               "c4", "world", "worldspawn", "planted_c4"}
GROUPS = ("normal", "thrusmoke", "penetrated")


def kill_shots(parsed) -> pd.DataFrame:
    """Kills by a hitscan weapon, with the killer's last weapon_fire tick (fallback: kill tick)."""
    k = parsed.kills
    k = k[~k["post_match"] & ~k["is_suicide"] & ~k["is_team_kill"] & ~k["weapon"].isin(NON_HITSCAN)].copy()
    by = {s: np.sort(g["tick"].to_numpy()) for s, g in parsed.shots.groupby("shooter_id")}
    fire = []
    for s, t in zip(k["attacker_id"], k["tick"]):
        arr = by.get(s)
        i = -1 if arr is None else np.searchsorted(arr, t, side="right") - 1
        fire.append(int(arr[i]) if i >= 0 and t - arr[i] <= FIRE_LOOKBACK_TICKS else int(t))
    k["fire_tick"] = fire
    pen, smoke = k["wallbang"].astype(bool), k["through_smoke"].astype(bool)
    k["group"] = np.select([pen, smoke], ["penetrated", "thrusmoke"], default="normal")
    return k.reset_index(drop=True)


def configs(parsed, mesh) -> dict[str, object]:
    smokes = SmokeIndex.from_table(parsed.smokes, parsed.tickrate)
    return {
        "spotted (game)": SpottedBackend(),
        "raycast LOS": RaycastBackend(mesh, smokes=None, fov_deg=None, lag_window=0),
        "+ lag window": RaycastBackend(mesh, smokes=None, fov_deg=None),
        "+ smoke": RaycastBackend(mesh, smokes=smokes, fov_deg=None),
        "+ FOV (full)": RaycastBackend(mesh, smokes=smokes),
    }


def analyse(path: Path) -> dict:
    from demoparser2 import DemoParser

    from impactagent.parse.demo import _demo_file, parse_demo

    t0 = time.perf_counter()
    parsed = parse_demo(path)
    t_parse = time.perf_counter() - t0
    k = kill_shots(parsed)
    t0 = time.perf_counter()
    mesh = load_mesh(parsed.map_name, parsed.client_build)
    t_mesh = time.perf_counter() - t0
    cfg = configs(parsed, mesh)
    need = set()
    for b in cfg.values():
        need |= b.ticks_needed(k["fire_tick"])
    t0 = time.perf_counter()
    with _demo_file(path) as (dem, _sha):
        parser = DemoParser(str(dem))
        states = TickStates.load(parser, need, spotted=True)
        del parser
    t_states = time.perf_counter() - t0

    q = k.rename(columns={"attacker_id": "observer_id", "victim_id": "target_id"})
    table, timing = {}, {}
    for name, b in cfg.items():
        t0 = time.perf_counter()
        r = check_pairs(b, states, q, tick_col="fire_tick")
        timing[name] = (time.perf_counter() - t0, getattr(b, "rays", 0))
        for g in GROUPS:
            v = r.loc[r["group"] == g, "visible"]
            table[(name, g)] = (int(v.sum()), int(v.notna().sum()))
        if name == "+ lag window":
            offsets = r.loc[r["group"] == "normal", "seen_offset"].value_counts(dropna=False).sort_index()
        if name == "+ FOV (full)":
            misses = r[(r["group"] == "normal") & (r["visible"] == False)]  # noqa: E712
    return {"map": parsed.map_name, "build": parsed.client_build, "kills": len(k), "smokes": len(parsed.smokes),
            "table": table, "timing": timing, "offsets": offsets, "misses": misses,
            "parse_s": t_parse, "mesh_s": t_mesh, "states_s": t_states, "state_ticks": len(need)}


def run(paths: list[Path]) -> int:
    results = [analyse(Path(p)) for p in paths]
    print("\n| map | backend | normal | thrusmoke | penetrated |\n|---|---|---|---|---|")
    for r in results:
        for name in dict.fromkeys(n for n, _ in r["table"]):
            cells = []
            for g in GROUPS:
                v, n = r["table"][(name, g)]
                cells.append(f"{v / n * 100:.1f}% ({v}/{n})" if n else "n/a")
            print(f"| {r['map']} | {name} | " + " | ".join(cells) + " |")
    print("\n| map | build | kills | smokes | parse s | mesh s | tick states s (ticks) | check s per backend (rays) |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        tm = ", ".join(f"{n}: {s:.3f}" + (f" ({rays})" if rays else "") for n, (s, rays) in r["timing"].items())
        print(f"| {r['map']} | {r['build']} | {r['kills']} | {r['smokes']} | {r['parse_s']:.1f} | {r['mesh_s']:.2f} | "
              f"{r['states_s']:.1f} ({r['state_ticks']}) | {tm} |")
    for r in results:
        print(f"\n{r['map']}: normal kills, first lag-comp offset seen: "
              + ", ".join(f"{'none' if pd.isna(o) else int(o)}t x{n}" for o, n in r["offsets"].items()))
        m = r["misses"]
        if len(m):
            print(f"{r['map']}: normal kills not seen with the full raycast ({len(m)}):")
            print(m[["round_no", "tick", "fire_tick", "weapon", "attacker_place", "victim_place"]].to_string(index=False))
    return 0
