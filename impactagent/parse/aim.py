"""Shot features and engagements (data-model §2.3 `shots`, §2.4 `engagements`).

Visibility comes from impactagent.visibility; tick states are read only for the ticks a shot
or a damage needs and dropped afterwards (no tick data is stored).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from impactagent.constants import (
    ENGAGEMENT_GAP_TICKS,
    ENGAGEMENT_LOOKBACK_SECONDS,
    FIRST_BULLET_GAP_SECONDS,
    GUNS,
    MACHINE_GUNS,
    PISTOLS,
    RIFLES,
    SHOTGUNS,
    SMGS,
    SNIPERS,
    SPRAY_MAX_GAP_SECONDS,
)
from impactagent.visibility import VisibilityBackend
from impactagent.visibility.geometry import view_dir
from impactagent.visibility.states import TickStates

ENGAGEMENT_COLUMNS = [
    "engagement_id", "round_no", "attacker_id", "victim_id", "first_seen_tick", "first_damage_tick",
    "last_damage_tick", "kill_tick", "ttd_ms", "ttk_ms", "crosshair_err_deg", "shots", "hits", "outcome",
]


def weapon_class(w: pd.Series) -> pd.Series:
    out = pd.Series("other", index=w.index, dtype="object")
    for cls, names in (("rifle", RIFLES), ("sniper", SNIPERS), ("smg", SMGS), ("pistol", PISTOLS),
                       ("shotgun", SHOTGUNS), ("mg", MACHINE_GUNS)):
        out[w.isin(names)] = cls
    out[w.astype("string").str.contains("knife|bayonet", na=False)] = "melee"
    return out


def gun_damages(damages: pd.DataFrame) -> pd.DataFrame:
    """Gun damage on enemies (no team damage, grenades, knife)."""
    d = damages
    return d[d["weapon"].isin(GUNS) & d["attacker_id"].notna() & ~d["is_team"]]


def needed_ticks(shots: pd.DataFrame, damages: pd.DataFrame, backend: VisibilityBackend, tickrate: int) -> set[int]:
    look = int(ENGAGEMENT_LOOKBACK_SECONDS * tickrate)
    base = {int(t) for t in shots.loc[shots["weapon"].isin(GUNS), "tick"]}
    base |= {int(t) - m for t in gun_damages(damages)["tick"] for m in range(look + 1)}
    return backend.ticks_needed(base)


def _enemies(player_rounds_side: pd.DataFrame) -> tuple[dict, pd.Series]:
    by = {(r, s): list(g["steam_id"]) for (r, s), g in player_rounds_side.groupby(["round_no", "side"])}
    side = player_rounds_side.set_index(["round_no", "steam_id"])["side"]
    return by, side


def build_shots(shots: pd.DataFrame, damages: pd.DataFrame, kills: pd.DataFrame, player_rounds_side: pd.DataFrame,
                states: TickStates, backend: VisibilityBackend, tickrate: int) -> pd.DataFrame:
    """Add per-shot features to the shots table.

    aim_shot: the shots Leetify counts in shots_fired / accuracy: guns except shotguns, and not
      fired in the tick the shooter died (mirage holdout: 7 + 6 shots, inferno has none).

    hit / hit_head / hit_victim_id: a gun shot "hits" when its shooter hurt an enemy with a gun in
      the same tick (every player_hurt in inferno+mirage has a weapon_fire in the same tick).
      Shotgun pellets / wallbangs through 2 players = one hit. hit_head only if EVERY hurt of the
      shot is a head hit (a bullet through a head into a 2nd player's chest is not a head hit:
      inferno Wagga r11, mirage PeterGooners r13; "last hurt of the shot" fits as well).
    enemy_spotted: any enemy alive and visible to the shooter at the shot tick (backend).
    spray_id / shot_index_in_spray / spray_len: consecutive shots of one weapon, gap <= SPRAY_MAX_GAP_SECONDS.
    first_bullet: no shot by the player in the FIRST_BULLET_GAP_SECONDS before.
    """
    s = shots.sort_values(["shooter_id", "tick"], kind="mergesort").reset_index(drop=True).copy()
    s["weapon_class"] = weapon_class(s["weapon"])
    died = set(zip(kills["victim_id"], kills["tick"]))
    s["died_this_tick"] = [(a, int(t)) in died for a, t in zip(s["shooter_id"], s["tick"])]
    s["aim_shot"] = s["weapon"].isin(GUNS) & ~s["weapon"].isin(SHOTGUNS) & ~s["died_this_tick"]
    d = gun_damages(damages)
    hits = d.groupby(["attacker_id", "tick"]).agg(
        hit_victim_id=("victim_id", "first"), hit_head=("hitgroup", lambda h: bool((h == "head").all())))
    key = pd.MultiIndex.from_arrays([s["shooter_id"], s["tick"]])
    is_gun = s["weapon"].isin(GUNS).to_numpy()
    hv = hits["hit_victim_id"].reindex(key).to_numpy()
    s["hit_victim_id"] = np.where(is_gun, hv, None)
    s["hit"] = s["hit_victim_id"].notna()
    s["hit_head"] = (hits["hit_head"].reindex(key).fillna(False).to_numpy(dtype=bool)) & is_gun

    enemies, side = _enemies(player_rounds_side)
    spotted = []
    for r, t, a, gun in zip(s["round_no"], s["tick"], s["shooter_id"], is_gun):
        my = side.get((r, a))
        if not gun or my is None:
            spotted.append(False)
            continue
        foes = enemies.get((r, "T" if my == "CT" else "CT"), [])
        spotted.append(any(backend.sees(states, int(t), a, e).visible for e in foes))
    s["enemy_spotted"] = spotted

    g = s.groupby("shooter_id")
    gap = s["tick"] - g["tick"].shift()
    gap_max = int(round(SPRAY_MAX_GAP_SECONDS * tickrate))
    new = (gap.isna() | (gap > gap_max) | (g["weapon"].shift() != s["weapon"]) | (g["round_no"].shift() != s["round_no"]))
    s["spray_id"] = np.cumsum(new.fillna(True).to_numpy(dtype=bool))
    s["shot_index_in_spray"] = s.groupby("spray_id").cumcount()
    s["spray_len"] = s.groupby("spray_id")["tick"].transform("size")
    s["first_bullet"] = (gap.isna() | (gap >= int(round(FIRST_BULLET_GAP_SECONDS * tickrate)))).fillna(True).to_numpy(dtype=bool)
    return s


def _angle(v1, v2) -> float:
    c = sum(a * b for a, b in zip(v1, v2))
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, c)))))


def build_engagements(shots: pd.DataFrame, damages: pd.DataFrame, kills: pd.DataFrame, states: TickStates,
                      backend: VisibilityBackend, tickrate: int) -> pd.DataFrame:
    """One row per engagement A -> B that has gun damage (spec §1.4/1.5).

    For each gun damage A -> B seen at the damage tick, walk back tick by tick while A sees B
    (gaps <= ENGAGEMENT_GAP_TICKS) to get first_seen. Damages with the same (A, B, first_seen)
    form one engagement. Damages not seen at their tick (wallbang / smoke) are not in any
    engagement; a run still visible at the lookback limit gets first_seen = NA (>= limit).
    v1 has no engagements without damage (`no_damage` / `died` outcomes come later).
    """
    look = int(ENGAGEMENT_LOOKBACK_SECONDS * tickrate)
    d = gun_damages(damages).drop_duplicates(["attacker_id", "victim_id", "tick"]).sort_values("tick")
    kill_keys = set(zip(kills["attacker_id"], kills["victim_id"], kills["tick"]))
    rows = []
    for r in d.itertuples(index=False):
        t, a, v = int(r.tick), r.attacker_id, r.victim_id
        if not backend.sees(states, t, a, v).visible:
            continue
        first, miss, m = t, 0, 1
        while m <= look:
            if backend.sees(states, t - m, a, v).visible:
                first, miss = t - m, 0
            elif (miss := miss + 1) > ENGAGEMENT_GAP_TICKS:
                break
            m += 1
        rows.append((r.round_no, a, v, t, first if m <= look else -1, (a, v, t) in kill_keys))
    if not rows:
        return pd.DataFrame(columns=ENGAGEMENT_COLUMNS)
    e = pd.DataFrame(rows, columns=["round_no", "attacker_id", "victim_id", "tick", "first_seen_tick", "kill"])
    g = e.groupby(["round_no", "attacker_id", "victim_id", "first_seen_tick"], sort=False)
    eng = g.agg(first_damage_tick=("tick", "min"), last_damage_tick=("tick", "max"), hits=("tick", "size")).reset_index()
    kt = e[e["kill"]].groupby(["round_no", "attacker_id", "victim_id", "first_seen_tick"])["tick"].min()
    eng["kill_tick"] = [kt.get(k) for k in zip(eng["round_no"], eng["attacker_id"], eng["victim_id"], eng["first_seen_tick"])]
    eng["kill_tick"] = eng["kill_tick"].astype("Int64")
    eng["first_seen_tick"] = eng["first_seen_tick"].where(eng["first_seen_tick"] >= 0).astype("Int64")
    ms = 1000 / tickrate
    eng["ttd_ms"] = (eng["first_damage_tick"] - eng["first_seen_tick"]).astype("Float64") * ms
    eng["ttk_ms"] = (eng["kill_tick"] - eng["first_seen_tick"]).astype("Float64") * ms
    cerr = []
    for fs, fd, a in zip(eng["first_seen_tick"], eng["first_damage_tick"], eng["attacker_id"]):
        o0 = states.get(int(fs), a) if pd.notna(fs) else None
        o1 = states.get(int(fd), a)
        cerr.append(_angle(view_dir(o0[4], o0[5]), view_dir(o1[4], o1[5])) if o0 and o1 else np.nan)
    eng["crosshair_err_deg"] = cerr
    sh = shots[shots["weapon"].isin(GUNS)]
    by = {sid: np.sort(g["tick"].to_numpy()) for sid, g in sh.groupby("shooter_id")}
    n_shots = []
    for a, fs, fd, last in zip(eng["attacker_id"], eng["first_seen_tick"], eng["first_damage_tick"], eng["last_damage_tick"]):
        arr = by.get(a, np.array([], dtype=int))
        lo = int(fs) if pd.notna(fs) else int(fd) - look
        n_shots.append(int(((arr >= lo) & (arr <= int(last))).sum()))
    eng["shots"] = n_shots
    eng["outcome"] = np.where(eng["kill_tick"].notna(), "kill", "damaged")
    eng = eng.sort_values(["round_no", "first_damage_tick"]).reset_index(drop=True)
    eng["engagement_id"] = np.arange(len(eng))
    return eng[ENGAGEMENT_COLUMNS]


def build_aim_tables(parser, shots, damages, kills, player_rounds_side, smokes, map_name, client_build,
                     tickrate, warnings: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """-> (shots with features, engagements, backend name). Raycast if awpy is installed, else spotted."""
    from impactagent.visibility import RaycastBackend, SmokeIndex, SpottedBackend, load_mesh

    try:
        backend: VisibilityBackend = RaycastBackend(load_mesh(map_name, client_build),
                                                    smokes=SmokeIndex.from_table(smokes, tickrate))
    except (ImportError, FileNotFoundError, ValueError) as exc:
        warnings.append(f"raycast visibility unavailable ({exc}); using game spotted")
        backend = SpottedBackend()
    states = TickStates.load(parser, needed_ticks(shots, damages, backend, tickrate), spotted=backend.needs_spotted)
    k = kills[~kills["post_match"]] if "post_match" in kills else kills
    s = build_shots(shots, damages, k, player_rounds_side, states, backend, tickrate)
    e = build_engagements(s, damages, k, states, backend, tickrate)
    # link shots to engagements: shots of A between first_seen and his last damage on B
    look = int(ENGAGEMENT_LOOKBACK_SECONDS * tickrate)
    eid = pd.array([pd.NA] * len(s), dtype="Int64")
    for x in e.itertuples(index=False):
        lo = int(x.first_seen_tick) if pd.notna(x.first_seen_tick) else int(x.first_damage_tick) - look
        m = ((s["shooter_id"] == x.attacker_id) & (s["tick"] >= lo) & (s["tick"] <= int(x.last_damage_tick))).to_numpy()
        eid[m] = x.engagement_id
    s["engagement_id"] = eid
    return s, e, backend.name
