"""Spike: line-of-sight for every kill using awpy's VisibilityChecker.

Not part of the impactagent package. For each kill, cast rays from the killer's eye to
the victim's head, chest and feet; any clear ray = "visible". Several modes are compared:

  death_guess    positions at the death tick, eye = 64 / 46 interpolated by duck_amount (v0)
  death_real     positions at the death tick, eye = 64 + m_flDuckViewOffset (real duck offset)
  fire           positions at the killer's last weapon_fire tick before the kill (offset 0)
  fire_rw_victim killer at the fire tick, victim rewound 0..8 ticks (lag-compensation style)
  fire_rw_both   killer and victim both rewound 0..8 ticks
  final          fire_rw_victim OR fire_rw_both

For kills not visible at the fire tick (before rewinding), the first mesh hit along each ray is found by bisection
(awpy has no hit-point API) and reported as distance from the killer's eye and from the
victim's target point.

Usage:
    python scripts/visibility_spike.py DEMO [DEMO ...] [--csv OUT_DIR] [--examples N]

Needs `pip install -e .[visibility]` (awpy>=3.1). Map meshes are cached under
~/.awpy/<ClientVersion>/ (AWPY_DATA_DIR moves it). The mesh release is picked from the
demo header's game_directory (".../csgo_v2000940/...") so geometry matches the build.

Eye height: the demo does not network m_vecViewOffset; it does network
CCSPlayer_MovementServices.m_flDuckViewOffset (0 standing .. -18 fully crouched), so
eye z = origin z + 64 + m_flDuckViewOffset. Only the 64 standing base is a constant.
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
MAX_REWIND = 8  # ticks
FIRE_LOOKBACK = 192  # ticks (3 s): last weapon_fire of the killer before the kill
NEAR_UNITS = 16.0  # a hit this close to an end point hints at player clip / wrong eye height
DUCK_VIEW_OFFSET = "CCSPlayerPawn.CCSPlayer_MovementServices.m_flDuckViewOffset"
POS_PROPS = ["X", "Y", "Z", "duck_amount", DUCK_VIEW_OFFSET]
RAYS = ("head", "chest", "feet")
MODES = ("death_guess", "death_real", "fire", "fire_rw_victim", "fire_rw_both", "final")

NON_HITSCAN = {
    "hegrenade", "flashbang", "smokegrenade", "decoy", "molotov", "incgrenade", "inferno",
    "c4", "world", "worldspawn", "planted_c4",
}


# --------------------------------------------------------------------------- geometry helpers

def eye_guess(duck_amount: float) -> float:
    d = 0.0 if np.isnan(duck_amount) else min(max(duck_amount, 0.0), 1.0)
    return EYE_STAND - (EYE_STAND - EYE_CROUCH) * d


def eye_real(duck_view_offset: float) -> float:
    return EYE_STAND + (0.0 if np.isnan(duck_view_offset) else duck_view_offset)


def ray_ends(att: tuple, vic: tuple, real_eye: bool) -> tuple[tuple, dict[str, tuple]]:
    """att / vic = (x, y, z, duck_amount, duck_view_offset)."""
    eh = eye_real if real_eye else eye_guess
    ax, ay, az, ad, ao = att
    vx, vy, vz, vd, vo = vic
    a = (ax, ay, az + eh(ao if real_eye else ad))
    ve = eh(vo if real_eye else vd)
    return a, {"head": (vx, vy, vz + ve), "chest": (vx, vy, vz + CHEST_FRACTION * ve), "feet": (vx, vy, vz + FEET_OFFSET)}


def first_hit(vc: VisibilityChecker, a: tuple, b: tuple, iters: int = 24) -> float | None:
    """Distance from `a` to the first mesh hit on segment a→b (None if clear). Bisection:
    the prefix a→p is occluded iff a triangle crosses it, which is monotonic in |p - a|."""
    if vc.is_visible(a, b):
        return None
    va, vb = np.asarray(a, float), np.asarray(b, float)
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        mid = (lo + hi) / 2
        if vc.is_visible(a, tuple(va + (vb - va) * mid)):
            lo = mid
        else:
            hi = mid
    return hi * float(np.linalg.norm(vb - va))


# --------------------------------------------------------------------------- demo data

def demo_extras(dem: Path, ticks: set[int]) -> tuple[int | None, dict]:
    """(ClientVersion from header, {(tick, steam_id): (x, y, z, duck_amount, duck_view_offset)})."""
    dp = DemoParser(str(dem))
    header = dp.parse_header() or {}
    m = re.search(r"csgo_v(\d+)", header.get("game_directory", ""))
    df = pd.DataFrame(dp.parse_ticks(POS_PROPS, ticks=sorted(t for t in ticks if t >= 0)))
    del dp
    df["sid"] = df["steamid"].astype(str)
    pos = {
        (int(t), s): (x, y, z, da, dvo)
        for t, s, x, y, z, da, dvo in zip(df["tick"], df["sid"], df["X"], df["Y"], df["Z"], df["duck_amount"], df[DUCK_VIEW_OFFSET])
    }
    return (int(m.group(1)) if m else None), pos


def pick_mesh_version(build: int | None, map_name: str) -> int | None:
    if build is None:
        return None
    try:
        awpy_data.mesh_path(map_name, build)
        return build
    except FileNotFoundError:
        print(f"  no awpy-data release {build} for {map_name}; using newest cached")
        return None


def last_fire_ticks(kills: pd.DataFrame, shots: pd.DataFrame) -> list[int | None]:
    by_shooter = {sid: np.sort(g["tick"].to_numpy()) for sid, g in shots.groupby(shots["shooter_id"].astype(str))}
    out = []
    for sid, t in zip(kills["attacker_id"], kills["tick"]):
        arr = by_shooter.get(sid)
        if arr is None:
            out.append(None)
            continue
        i = np.searchsorted(arr, t, side="right") - 1
        out.append(int(arr[i]) if i >= 0 and t - arr[i] <= FIRE_LOOKBACK else None)
    return out


# --------------------------------------------------------------------------- analysis

def analyse(path: Path, csv_dir: Path | None) -> dict:
    t0 = time.perf_counter()
    parsed = parse_demo(path)

    k = parsed.kills
    k = k[~k["post_match"] & ~k["is_suicide"] & ~k["is_team_kill"]].copy()
    k = k[~k["weapon"].isin(NON_HITSCAN)].reset_index(drop=True)
    k["attacker_id"] = k["attacker_id"].astype(str)
    k["victim_id"] = k["victim_id"].astype(str)
    k["fire_tick"] = last_fire_ticks(k, parsed.shots)
    base = [int(f) if f is not None else int(t) for f, t in zip(k["fire_tick"], k["tick"])]
    need = set(k["tick"].astype(int)) | {b - d for b in base for d in range(MAX_REWIND + 1)}

    with _demo_file(path) as (dem, _sha):
        build, pos = demo_extras(dem, need)
    t_parse = time.perf_counter() - t0

    version = pick_mesh_version(build, parsed.map_name)
    t0 = time.perf_counter()
    vc = VisibilityChecker(parsed.map_name, version=version)
    t_load = time.perf_counter() - t0

    n_rays = 0
    t_rays = 0.0

    def visible(att_key, vic_key, real_eye: bool) -> bool | None:
        nonlocal n_rays, t_rays
        att, vic = pos.get(att_key), pos.get(vic_key)
        if att is None or vic is None or np.isnan(att[0]) or np.isnan(vic[0]):
            return None
        a, ends = ray_ends(att, vic, real_eye)
        s = time.perf_counter()
        hit = False
        for name in RAYS:
            n_rays += 1
            if vc.is_visible(a, ends[name]):
                hit = True
                break
        t_rays += time.perf_counter() - s
        return hit

    rows = []
    for i, r in k.iterrows():
        att, vic, t, b = r["attacker_id"], r["victim_id"], int(r["tick"]), base[i]
        row = {
            "death_guess": visible((t, att), (t, vic), real_eye=False),
            "death_real": visible((t, att), (t, vic), real_eye=True),
            "fire": visible((b, att), (b, vic), real_eye=True),
        }
        row["rw_victim_offset"] = next((d for d in range(MAX_REWIND + 1) if visible((b, att), (b - d, vic), True)), None)
        row["rw_both_offset"] = next((d for d in range(MAX_REWIND + 1) if visible((b - d, att), (b - d, vic), True)), None)
        row["fire_rw_victim"] = row["rw_victim_offset"] is not None
        row["fire_rw_both"] = row["rw_both_offset"] is not None
        row["final"] = row["fire_rw_victim"] or row["fire_rw_both"]
        # hit diagnostics for kills not visible at the fire tick (before rewinding), real eye
        if row["fire"] is False and (b, att) in pos and (b, vic) in pos:
            a, ends = ray_ends(pos[(b, att)], pos[(b, vic)], real_eye=True)
            for name in RAYS:
                row[f"hit_from_killer_{name}"] = first_hit(vc, a, ends[name])
                row[f"hit_from_victim_{name}"] = first_hit(vc, ends[name], a)
            row["att_eye_z"] = a[2] - pos[(b, att)][2]
            row["vic_eye_z"] = ends["head"][2] - pos[(b, vic)][2]
        rows.append(row)
    k = pd.concat([k, pd.DataFrame(rows)], axis=1)

    names = parsed.players.set_index("steam_id")["name"]
    names.index = names.index.astype(str)
    rounds = parsed.rounds.set_index("round_no")
    k["attacker"] = k["attacker_id"].map(names)
    k["victim"] = k["victim_id"].map(names)
    k["round_time_s"] = (k["tick"] - k["round_no"].map(rounds["freeze_end_tick"])) / parsed.tickrate
    k["fire_lag"] = k["tick"] - pd.Series(base)
    k["distance"] = np.sqrt(
        (k["attacker_x"] - k["victim_x"]) ** 2 + (k["attacker_y"] - k["victim_y"]) ** 2 + (k["attacker_z"] - k["victim_z"]) ** 2
    )
    hk = [f"hit_from_killer_{n}" for n in RAYS if f"hit_from_killer_{n}" in k]
    hv = [f"hit_from_victim_{n}" for n in RAYS if f"hit_from_victim_{n}" in k]
    if hk:
        k["hit_killer_min"] = k[hk].min(axis=1)
        k["hit_victim_min"] = k[hv].min(axis=1)
        k["near"] = np.select(
            [k["hit_killer_min"] < NEAR_UNITS, k["hit_victim_min"] < NEAR_UNITS], ["killer", "victim"], default=""
        )
    if csv_dir is not None:
        csv_dir.mkdir(parents=True, exist_ok=True)
        k.to_csv(csv_dir / f"visibility_{parsed.map_name}_{parsed.sha256[:8]}.csv", index=False)

    pen = k["wallbang"].astype(bool)
    smoke = k["through_smoke"].astype(bool)
    groups = {"normal": ~pen & ~smoke, "thrusmoke": smoke, "penetrated": pen}
    table = {}
    for mode in MODES:
        for g, mask in groups.items():
            v = k.loc[mask, mode].astype("boolean")
            table[(mode, g)] = (int(v.sum()), int(v.notna().sum()))

    return {
        "map": parsed.map_name,
        "build": build,
        "mesh_version": version or awpy_data.resolve_version(),
        "kills": len(k),
        "no_fire": int(k["fire_tick"].isna().sum()),
        "table": table,
        "offsets_victim": k.loc[groups["normal"] & ~k["fire"].astype(bool), "rw_victim_offset"].value_counts(dropna=False).sort_index(),
        "offsets_both": k.loc[groups["normal"] & ~k["fire"].astype(bool), "rw_both_offset"].value_counts(dropna=False).sort_index(),
        "misses": k[groups["normal"] & ~k["final"]].sort_values("tick"),
        "fire_misses": k[groups["normal"] & (k["fire"] == False)].sort_values("tick"),  # noqa: E712
        "fire_lag": k["fire_lag"].value_counts().sort_index(),
        "rays": n_rays,
        "us_per_ray": t_rays / max(n_rays, 1) * 1e6,
        "ray_s": t_rays,
        "load_s": t_load,
        "parse_s": t_parse,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demos", nargs="+", type=Path)
    ap.add_argument("--csv", type=Path, default=None, help="write per-kill CSV here (keep it in a gitignored dir)")
    ap.add_argument("--examples", type=int, default=10)
    args = ap.parse_args()

    results = [analyse(p, args.csv) for p in args.demos]

    print("\n| map | mode | normal | thrusmoke | penetrated |")
    print("|---|---|---|---|---|")
    for r in results:
        for mode in MODES:
            cells = []
            for g in ("normal", "thrusmoke", "penetrated"):
                v, n = r["table"][(mode, g)]
                cells.append(f"{v / n * 100:.1f}% ({v}/{n})" if n else "n/a")
            print(f"| {r['map']} | {mode} | " + " | ".join(cells) + " |")

    print("\n| map | build / mesh | kills | no weapon_fire in 3s | rays | us/ray | ray s | mesh load s | parse s |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(
            f"| {r['map']} | {r['build']} / {r['mesh_version']} | {r['kills']} | {r['no_fire']} | {r['rays']} | "
            f"{r['us_per_ray']:.1f} | {r['ray_s']:.3f} | {r['load_s']:.2f} | {r['parse_s']:.1f} |"
        )

    cols = ["round_no", "tick", "fire_lag", "rw_victim_offset", "rw_both_offset", "round_time_s", "attacker", "victim", "weapon", "distance",
            "attacker_place", "victim_place", "att_eye_z", "vic_eye_z", "hit_killer_min", "hit_victim_min", "near"]
    with pd.option_context("display.width", 260, "display.max_columns", 30):
        for r in results:
            print(f"\n{r['map']}: normal kills not visible at fire tick -> first visible rewind offset (victim only / both)")
            print(pd.concat([r["offsets_victim"].rename("victim"), r["offsets_both"].rename("both")], axis=1).fillna(0).astype(int).to_string())
            lag = ", ".join(f"{int(a)}t x{b}" for a, b in r["fire_lag"].items())
            print(f"\n{r['map']}: kill tick - last weapon_fire tick: {lag}")
            f = r["fire_misses"]
            print(f"\n{r['map']}: normal kills NOT visible at the fire tick (before rewind) ({len(f)})")
            print(f[[c for c in cols if c in f]].head(args.examples).round(1).to_string(index=False))
            m = r["misses"]
            print(f"\n{r['map']}: normal kills still NOT visible ({len(m)})")
            print(m[[c for c in cols if c in m]].head(args.examples).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
