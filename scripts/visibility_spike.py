"""Spike: line-of-sight for every kill using awpy's VisibilityChecker.

Not part of the impactagent package. For each kill, cast rays from the killer's eye
to the victim's head, chest and feet at the kill tick; any clear ray = "visible".

Usage:
    python scripts/visibility_spike.py DEMO [DEMO ...] [--csv OUT_DIR] [--examples N]

Needs `pip install awpy` (>=3.1). Map meshes are cached under ~/.awpy/<ClientVersion>/
(set AWPY_DATA_DIR to move it). The mesh release is picked from the demo header's
game_directory (".../csgo_v2000940/...") so geometry matches the demo's build.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from awpy import VisibilityChecker
from awpy import data as awpy_data
from demoparser2 import DemoParser

from impactagent.parse.demo import _demo_file, parse_demo

EYE_STAND = 64.0
EYE_CROUCH = 46.0
FEET_OFFSET = 8.0  # above origin, so the ray does not graze the floor under the victim
CHEST_FRACTION = 0.72  # chest height as a fraction of eye height

NON_HITSCAN = {
    "hegrenade", "flashbang", "smokegrenade", "decoy", "molotov", "incgrenade", "inferno",
    "c4", "world", "worldspawn", "planted_c4",
}


def eye_height(duck: pd.Series) -> pd.Series:
    duck = duck.fillna(0.0).clip(0.0, 1.0)
    return EYE_STAND - (EYE_STAND - EYE_CROUCH) * duck


def demo_build(dem: Path) -> tuple[int | None, pd.DataFrame]:
    """(ClientVersion from header, duck_amount of attacker/victim per death)."""
    dp = DemoParser(str(dem))
    header = dp.parse_header() or {}
    m = re.search(r"csgo_v(\d+)", header.get("game_directory", ""))
    deaths = pd.DataFrame(dp.parse_event("player_death", player=["duck_amount"]))
    del dp
    cols = {"tick": "tick", "user_steamid": "victim_id", "attacker_duck_amount": "att_duck", "user_duck_amount": "vic_duck"}
    deaths = deaths[[c for c in cols if c in deaths]].rename(columns=cols)
    deaths["victim_id"] = deaths["victim_id"].astype(str)
    return (int(m.group(1)) if m else None), deaths


def pick_mesh_version(build: int | None, map_name: str) -> int | None:
    if build is None:
        return None
    try:
        awpy_data.mesh_path(map_name, build)
        return build
    except FileNotFoundError:
        print(f"  no awpy-data release {build} for {map_name}; using newest cached")
        return None


def analyse(path: Path, n_examples: int, csv_dir: Path | None) -> dict:
    t0 = time.perf_counter()
    parsed = parse_demo(path)
    with _demo_file(path) as (dem, _sha):
        build, duck = demo_build(dem)
    t_parse = time.perf_counter() - t0

    version = pick_mesh_version(build, parsed.map_name)
    t0 = time.perf_counter()
    vc = VisibilityChecker(parsed.map_name, version=version)
    t_load = time.perf_counter() - t0

    k = parsed.kills
    k = k[~k["post_match"] & ~k["is_suicide"] & ~k["is_team_kill"]].copy()
    k = k[~k["weapon"].isin(NON_HITSCAN)]
    k = k.dropna(subset=["attacker_x", "victim_x"])
    k["victim_id"] = k["victim_id"].astype(str)
    duck = duck.drop_duplicates(["tick", "victim_id"])
    k = k.merge(duck, on=["tick", "victim_id"], how="left")

    k["att_eye"] = eye_height(k["att_duck"])
    k["vic_eye"] = eye_height(k["vic_duck"])
    eye = list(zip(k["attacker_x"], k["attacker_y"], k["attacker_z"] + k["att_eye"]))
    targets = {
        "head": k["victim_z"] + k["vic_eye"],
        "chest": k["victim_z"] + CHEST_FRACTION * k["vic_eye"],
        "feet": k["victim_z"] + FEET_OFFSET,
    }

    n_rays = 0
    t0 = time.perf_counter()
    for name, z in targets.items():
        res = []
        for a, bx, by, bz in zip(eye, k["victim_x"], k["victim_y"], z):
            res.append(vc.is_visible(a, (bx, by, bz)))
        k[f"vis_{name}"] = res
        n_rays += len(res)
    t_rays = time.perf_counter() - t0
    k["visible"] = k[["vis_head", "vis_chest", "vis_feet"]].any(axis=1)

    pen = k["wallbang"].astype(bool)
    smoke = k["through_smoke"].astype(bool)
    normal = ~pen & ~smoke

    names = parsed.players.set_index("steam_id")["name"]
    rounds = parsed.rounds.set_index("round_no")
    k["attacker"] = k["attacker_id"].map(names)
    k["victim"] = k["victim_id"].map(names)
    k["round_time_s"] = (k["tick"] - k["round_no"].map(rounds["freeze_end_tick"])) / parsed.tickrate
    k["distance"] = np.sqrt(
        (k["attacker_x"] - k["victim_x"]) ** 2 + (k["attacker_y"] - k["victim_y"]) ** 2 + (k["attacker_z"] - k["victim_z"]) ** 2
    )
    if csv_dir is not None:
        csv_dir.mkdir(parents=True, exist_ok=True)
        k.to_csv(csv_dir / f"visibility_{parsed.map_name}_{parsed.sha256[:8]}.csv", index=False)

    def pct(mask) -> str:
        sub = k[mask]
        return f"{sub['visible'].mean() * 100:.1f}% ({int(sub['visible'].sum())}/{len(sub)})" if len(sub) else "n/a"

    misses = k[normal & ~k["visible"]].sort_values("tick")
    return {
        "demo": path.name,
        "map": parsed.map_name,
        "build": build,
        "mesh_version": version or awpy_data.resolve_version(),
        "triangles": vc.triangle_count,
        "kills": len(k),
        "normal": pct(normal),
        "penetrated": pct(pen),
        "thrusmoke": pct(smoke),
        "head_only_normal": f"{k.loc[normal, 'vis_head'].mean() * 100:.1f}%",
        "rays": n_rays,
        "us_per_ray": t_rays / n_rays * 1e6,
        "ray_s": t_rays,
        "load_s": t_load,
        "parse_s": t_parse,
        "misses": misses[
            ["round_no", "tick", "round_time_s", "attacker", "victim", "weapon", "distance",
             "attacker_place", "victim_place", "att_duck", "vic_duck", "vis_head", "vis_chest", "vis_feet"]
        ],
        "n_examples": n_examples,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demos", nargs="+", type=Path)
    ap.add_argument("--csv", type=Path, default=None, help="write per-kill CSV here (keep it in a gitignored dir)")
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args()

    results = [analyse(p, args.examples, args.csv) for p in args.demos]

    print("\n| map | build / mesh | tris | kills | normal visible | penetrated>0 visible | thrusmoke visible | head ray only (normal) | rays | us/ray | rays/match s | mesh load s | parse s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(
            f"| {r['map']} | {r['build']} / {r['mesh_version']} | {r['triangles']:,} | {r['kills']} | {r['normal']} | {r['penetrated']} | "
            f"{r['thrusmoke']} | {r['head_only_normal']} | {r['rays']} | {r['us_per_ray']:.1f} | {r['ray_s']:.3f} | {r['load_s']:.2f} | {r['parse_s']:.1f} |"
        )
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        for r in results:
            print(f"\n{r['map']}: normal kills judged NOT visible ({len(r['misses'])})")
            print(r["misses"].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
