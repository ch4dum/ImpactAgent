"""Parse a CS2 .dem into event tables (see docs/design/data-model.md).

Only events are kept; no per-tick position data.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from demoparser2 import DemoParser

from impactagent.constants import DEFAULT_TICKRATE, GRENADE_WEAPONS, SIDE_BY_TEAM_NUM

POS_PROPS = ["team_num", "last_place_name", "X", "Y", "Z"]


@dataclass
class ParsedDemo:
    path: Path
    sha256: str
    map_name: str
    tickrate: int
    rounds: pd.DataFrame
    players: pd.DataFrame
    player_rounds_side: pd.DataFrame
    kills: pd.DataFrame
    damages: pd.DataFrame
    shots: pd.DataFrame
    grenades: pd.DataFrame
    blinds: pd.DataFrame
    bomb: pd.DataFrame
    death_inventory: pd.DataFrame
    warnings: list[str] = field(default_factory=list)

    def tables(self) -> dict[str, pd.DataFrame]:
        return {
            "rounds": self.rounds,
            "players": self.players,
            "player_rounds_side": self.player_rounds_side,
            "kills": self.kills,
            "damages": self.damages,
            "shots": self.shots,
            "grenades": self.grenades,
            "blinds": self.blinds,
            "bomb": self.bomb,
            "death_inventory": self.death_inventory,
        }


# --------------------------------------------------------------------------- helpers

def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _event(parser: DemoParser, name: str, player: list[str] | None = None) -> pd.DataFrame:
    try:
        df = parser.parse_event(name, player=player or [])
    except Exception:  # event not present in this demo
        return pd.DataFrame()
    if df is None:
        return pd.DataFrame()
    return pd.DataFrame(df)


def _sid(s: pd.Series) -> pd.Series:
    """Normalise steam ids to strings; bots / world become None."""
    out = s.astype("string")
    return out.where(~out.isin(["0", "<NA>", "nan", "None"]), None)


def _strip_weapon(s: pd.Series) -> pd.Series:
    return s.astype("string").str.lower().str.replace("weapon_", "", regex=False)


def _side(team_num: pd.Series) -> pd.Series:
    return team_num.map(SIDE_BY_TEAM_NUM)


def _winner_side(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).upper()
    if s in ("CT", "3"):
        return "CT"
    if s in ("T", "TERRORIST", "2"):
        return "T"
    return None


# --------------------------------------------------------------------------- rounds

def _build_rounds(parser: DemoParser, tickrate: int, warnings: list[str]) -> pd.DataFrame:
    ends = _event(parser, "round_end")
    if ends.empty:
        raise ValueError("No round_end events found in demo")
    ends = ends.sort_values("tick").drop_duplicates("tick")
    ends["winner_side"] = ends["winner"].map(_winner_side) if "winner" in ends else None
    ends = ends[ends["winner_side"].notna()]

    match_start = _event(parser, "round_announce_match_start")
    start_tick = int(match_start["tick"].max()) if not match_start.empty else 0
    if match_start.empty:
        warnings.append("round_announce_match_start missing: warmup/knife filtering may be off")
    ends = ends[ends["tick"] > start_tick].reset_index(drop=True)

    starts = _event(parser, "round_start")
    start_ticks = np.sort(starts["tick"].unique()) if not starts.empty else np.array([])
    freeze = _event(parser, "round_freeze_end")
    freeze_ticks = np.sort(freeze["tick"].unique()) if not freeze.empty else np.array([])

    rows = []
    prev_end = start_tick
    for i, r in ends.iterrows():
        end = int(r["tick"])
        cand = start_ticks[(start_ticks >= prev_end) & (start_ticks < end)]
        rstart = int(cand.max()) if len(cand) else prev_end
        fcand = freeze_ticks[(freeze_ticks >= rstart) & (freeze_ticks < end)]
        fz = int(fcand.min()) if len(fcand) else rstart
        rows.append(
            {
                "round_no": i + 1,
                "start_tick": rstart,
                "freeze_end_tick": fz,
                "end_tick": end,
                "winner_side": r["winner_side"],
                "win_reason": r.get("reason"),
            }
        )
        prev_end = end
    rounds = pd.DataFrame(rows)
    # Window used to assign events (exit frags after round_end stay in the round).
    rounds["next_start_tick"] = rounds["start_tick"].shift(-1).fillna(np.iinfo(np.int64).max).astype("int64")
    return rounds


def _assign_round(df: pd.DataFrame, rounds: pd.DataFrame) -> pd.DataFrame:
    """Attach round_no to events; drop events outside official rounds (warmup etc.)."""
    if df.empty:
        df = df.copy()
        df["round_no"] = pd.Series(dtype="int64")
        return df
    df = df.sort_values("tick").copy()
    df["tick"] = df["tick"].astype("int64")
    r = rounds[["round_no", "start_tick", "freeze_end_tick", "next_start_tick"]].sort_values("start_tick")
    out = pd.merge_asof(df, r, left_on="tick", right_on="start_tick", direction="backward")
    out = out[out["round_no"].notna() & (out["tick"] < out["next_start_tick"])]
    out["round_no"] = out["round_no"].astype("int64")
    return out.drop(columns=["start_tick", "next_start_tick"])


# --------------------------------------------------------------------------- main

def parse_demo(path: str | Path) -> ParsedDemo:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    warnings: list[str] = []
    parser = DemoParser(str(path))
    header = parser.parse_header() or {}
    map_name = header.get("map_name", "unknown")
    tickrate = DEFAULT_TICKRATE

    rounds = _build_rounds(parser, tickrate, warnings)

    # ---- sides per round (team_num of every player at freeze end)
    snap = pd.DataFrame(parser.parse_ticks(["team_num"], ticks=rounds["freeze_end_tick"].tolist()))
    snap["steam_id"] = _sid(snap["steamid"])
    snap = snap[snap["steam_id"].notna() & snap["team_num"].isin([2, 3])]
    snap = snap.merge(rounds[["round_no", "freeze_end_tick"]], left_on="tick", right_on="freeze_end_tick")
    snap["side"] = _side(snap["team_num"])
    player_rounds_side = snap[["round_no", "steam_id", "name", "side"]].reset_index(drop=True)

    # Team "a" = players on CT in round 1.
    r1 = player_rounds_side[player_rounds_side["round_no"] == 1]
    team_a = set(r1.loc[r1["side"] == "CT", "steam_id"])
    players = (
        player_rounds_side.groupby("steam_id")
        .agg(name=("name", "last"), rounds_played=("round_no", "nunique"))
        .reset_index()
    )
    players["team"] = np.where(players["steam_id"].isin(team_a), "a", "b")
    side_by_round = player_rounds_side.groupby("round_no").apply(
        lambda g: "a" if (g.loc[g["side"] == "CT", "steam_id"].isin(team_a)).any() else "b",
        include_groups=False,
    )
    rounds["ct_team"] = rounds["round_no"].map(side_by_round)
    rounds["t_team"] = np.where(rounds["ct_team"] == "a", "b", "a")

    # ---- kills
    k = _event(parser, "player_death", POS_PROPS)
    k = _assign_round(k, rounds)
    kills = pd.DataFrame(
        {
            "round_no": k["round_no"],
            "tick": k["tick"],
            "attacker_id": _sid(k["attacker_steamid"]),
            "victim_id": _sid(k["user_steamid"]),
            "assister_id": _sid(k["assister_steamid"]) if "assister_steamid" in k else None,
            "flash_assist": k.get("assistedflash", False),
            "weapon": _strip_weapon(k["weapon"]),
            "headshot": k.get("headshot", False),
            "wallbang": k.get("penetrated", 0).fillna(0).astype(int) > 0 if "penetrated" in k else False,
            "through_smoke": k.get("thrusmoke", False),
            "noscope": k.get("noscope", False),
            "attacker_blind": k.get("attackerblind", False),
            "attacker_side": _side(k["attacker_team_num"]) if "attacker_team_num" in k else None,
            "victim_side": _side(k["user_team_num"]) if "user_team_num" in k else None,
            "attacker_place": k.get("attacker_last_place_name"),
            "victim_place": k.get("user_last_place_name"),
            "attacker_x": k.get("attacker_X"), "attacker_y": k.get("attacker_Y"), "attacker_z": k.get("attacker_Z"),
            "victim_x": k.get("user_X"), "victim_y": k.get("user_Y"), "victim_z": k.get("user_Z"),
        }
    ).reset_index(drop=True)
    kills["is_team_kill"] = kills["attacker_side"].notna() & (kills["attacker_side"] == kills["victim_side"])
    kills["is_suicide"] = kills["attacker_id"].isna() | (kills["attacker_id"] == kills["victim_id"])

    # ---- damages
    d = _event(parser, "player_hurt", ["team_num"])
    d = _assign_round(d, rounds)
    damages = pd.DataFrame(
        {
            "round_no": d["round_no"],
            "tick": d["tick"],
            "attacker_id": _sid(d["attacker_steamid"]),
            "victim_id": _sid(d["user_steamid"]),
            "weapon": _strip_weapon(d["weapon"]),
            "hitgroup": d.get("hitgroup"),
            "dmg_raw": d["dmg_health"].astype(int),
            "dmg_armor": d.get("dmg_armor"),
            "victim_hp_after": d["health"].astype(int),
            "attacker_side": _side(d["attacker_team_num"]) if "attacker_team_num" in d else None,
            "victim_side": _side(d["user_team_num"]) if "user_team_num" in d else None,
        }
    ).reset_index(drop=True)
    damages = damages.sort_values(["round_no", "victim_id", "tick"]).reset_index(drop=True)
    prev_hp = damages.groupby(["round_no", "victim_id"])["victim_hp_after"].shift(1).fillna(100)
    damages["dmg_effective"] = np.minimum(damages["dmg_raw"], prev_hp).astype(int)
    damages["is_team"] = damages["attacker_side"].notna() & (damages["attacker_side"] == damages["victim_side"])

    # ---- shots (velocity for counter-strafe later)
    s = _event(parser, "weapon_fire", ["team_num", "velocity_X", "velocity_Y", "ducking", "is_scoped"])
    s = _assign_round(s, rounds)
    shots = pd.DataFrame(
        {
            "round_no": s["round_no"],
            "tick": s["tick"],
            "shooter_id": _sid(s["user_steamid"]),
            "weapon": _strip_weapon(s["weapon"]),
            "speed_2d": np.hypot(s.get("user_velocity_X", 0), s.get("user_velocity_Y", 0)),
            "ducking": s.get("user_ducking"),
            "scoped": s.get("user_is_scoped"),
        }
    ).reset_index(drop=True)

    # ---- grenades thrown (from weapon_fire) + detonations
    g = shots[shots["weapon"].isin(GRENADE_WEAPONS.keys())].copy()
    grenades = pd.DataFrame(
        {
            "round_no": g["round_no"],
            "throw_tick": g["tick"],
            "thrower_id": g["shooter_id"],
            "weapon": g["weapon"],
            "type": g["weapon"].map(GRENADE_WEAPONS),
        }
    ).reset_index(drop=True)
    shots = shots[~shots["weapon"].isin(GRENADE_WEAPONS.keys())].reset_index(drop=True)

    det_frames = []
    for ev, gtype in [
        ("flashbang_detonate", "flash"),
        ("hegrenade_detonate", "he"),
        ("smokegrenade_detonate", "smoke"),
        ("inferno_startburn", "molotov"),
    ]:
        e = _event(parser, ev)
        if e.empty:
            continue
        e = _assign_round(e, rounds)
        det_frames.append(
            pd.DataFrame(
                {
                    "round_no": e["round_no"],
                    "tick": e["tick"],
                    "type": gtype,
                    "entity_id": e.get("entityid"),
                    "thrower_id": _sid(e["user_steamid"]) if "user_steamid" in e else None,
                    "x": e.get("x"), "y": e.get("y"), "z": e.get("z"),
                }
            )
        )
    detonations = pd.concat(det_frames, ignore_index=True) if det_frames else pd.DataFrame()

    # ---- blinds
    b = _event(parser, "player_blind", ["team_num"])
    b = _assign_round(b, rounds)
    blinds = pd.DataFrame(
        {
            "round_no": b["round_no"],
            "tick": b["tick"],
            "thrower_id": _sid(b["attacker_steamid"]),
            "victim_id": _sid(b["user_steamid"]),
            "duration": b["blind_duration"].astype(float),
            "entity_id": b.get("entityid"),
            "thrower_side": _side(b["attacker_team_num"]) if "attacker_team_num" in b else None,
            "victim_side": _side(b["user_team_num"]) if "user_team_num" in b else None,
        }
    ).reset_index(drop=True)
    blinds["is_teammate"] = blinds["thrower_side"] == blinds["victim_side"]

    # ---- bomb
    bomb_frames = []
    for ev, kind in [("bomb_planted", "plant"), ("bomb_defused", "defuse"), ("bomb_exploded", "explode")]:
        e = _event(parser, ev)
        if e.empty:
            continue
        e = _assign_round(e, rounds)
        bomb_frames.append(
            pd.DataFrame({"round_no": e["round_no"], "tick": e["tick"], "type": kind,
                          "steam_id": _sid(e["user_steamid"]) if "user_steamid" in e else None,
                          "site": e.get("site")})
        )
    bomb = pd.concat(bomb_frames, ignore_index=True) if bomb_frames else pd.DataFrame(columns=["round_no", "tick", "type", "steam_id", "site"])
    plants = bomb[bomb["type"] == "plant"].groupby("round_no")["tick"].min()
    rounds["plant_tick"] = rounds["round_no"].map(plants)

    # ---- inventory at death (unused utility)
    death_ticks = sorted(kills["tick"].unique().tolist())
    death_inventory = pd.DataFrame(columns=["tick", "steam_id", "inventory"])
    if death_ticks:
        # inventory is read one tick before death, while the player still holds it
        inv = pd.DataFrame(parser.parse_ticks(["inventory"], ticks=[t - 1 for t in death_ticks]))
        if not inv.empty:
            inv["steam_id"] = _sid(inv["steamid"])
            inv["tick"] = inv["tick"] + 1
            death_inventory = inv[["tick", "steam_id", "inventory"]]

    rounds = rounds.drop(columns=["next_start_tick"])
    grenades.attrs["detonations"] = detonations
    return ParsedDemo(
        path=path,
        sha256=_sha256(path),
        map_name=map_name,
        tickrate=tickrate,
        rounds=rounds,
        players=players,
        player_rounds_side=player_rounds_side,
        kills=kills,
        damages=damages,
        shots=shots,
        grenades=grenades,
        blinds=blinds,
        bomb=bomb,
        death_inventory=death_inventory,
        warnings=warnings,
    )
