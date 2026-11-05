"""Parse a CS2 .dem into event tables (see docs/design/data-model.md).

Only events are kept; no per-tick position data.
"""

from __future__ import annotations

import gc
import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from demoparser2 import DemoParser

from impactagent.constants import (
    DEFAULT_TICKRATE,
    GRENADE_WEAPONS,
    MAX_DEMO_BYTES,
    PARSE_TIMEOUT_SECONDS,
    SIDE_BY_TEAM_NUM,
    TRADE_WINDOW_SECONDS,
)
from impactagent.parse.aim import ENGAGEMENT_COLUMNS, build_aim_tables
from impactagent.parse.trades import build_trade_windows
from impactagent.visibility.smoke import SMOKE_COLUMNS, pair_smokes

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
    trade_windows: pd.DataFrame = field(default_factory=pd.DataFrame)
    smokes: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=SMOKE_COLUMNS))
    engagements: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=ENGAGEMENT_COLUMNS))
    visibility_backend: str = ""  # backend used for shots.enemy_spotted / engagements
    client_build: int | None = None  # csgo_v<build> from the header: picks the map mesh release
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
            "trade_windows": self.trade_windows,
            "smokes": self.smokes,
            "engagements": self.engagements,
        }


# --------------------------------------------------------------------------- helpers

_CHUNK = 1 << 20


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(_CHUNK):
            h.update(b)
    return h.hexdigest()


def _open_compressed(path: Path):
    """Binary stream that decompresses `path`, or None if it is a plain .dem."""
    suffix = path.suffix.lower()
    if suffix == ".bz2":
        import bz2
        return bz2.open(path, "rb")
    if suffix == ".gz":
        import gzip
        return gzip.open(path, "rb")
    if suffix == ".zst":
        try:
            import zstandard
        except ImportError as exc:
            raise ImportError("Reading .dem.zst needs the 'zstandard' package: pip install zstandard") from exc
        return zstandard.ZstdDecompressor().stream_reader(open(path, "rb"), closefd=True)
    return None


class DemoTooLargeError(ValueError):
    """The demo (after decompression) is bigger than the allowed maximum."""


class ParseTimeoutError(TimeoutError):
    """Parsing took longer than the allowed wall-clock time."""


@contextmanager
def _demo_file(path: Path, max_bytes: int | None = MAX_DEMO_BYTES):
    """Yield (path to a plain .dem, sha256 of the plain .dem).

    Compressed demos are streamed to a temp file that is removed afterwards, even on error.
    Decompression stops as soon as the output passes `max_bytes` (zip-bomb guard).
    The hash is taken while decompressing, so the same match hashes the same however it is packed.
    """
    stream = _open_compressed(path)
    if stream is None:
        if max_bytes is not None and path.stat().st_size > max_bytes:
            raise DemoTooLargeError(f"{path.name}: {path.stat().st_size} bytes > limit {max_bytes}")
        yield path, _sha256(path)
        return
    fd, tmp_name = tempfile.mkstemp(suffix=".dem", prefix="impactagent-")
    tmp = Path(tmp_name)
    try:
        h = hashlib.sha256()
        written = 0
        with stream, os.fdopen(fd, "wb") as out:
            while b := stream.read(_CHUNK):
                written += len(b)
                if max_bytes is not None and written > max_bytes:
                    raise DemoTooLargeError(f"{path.name}: decompressed size passed limit {max_bytes} bytes")
                h.update(b)
                out.write(b)
        yield tmp, h.hexdigest()
    finally:
        gc.collect()  # drop demoparser2 handles so Windows lets us delete the file
        try:
            tmp.unlink(missing_ok=True)
        except PermissionError:
            gc.collect()
            tmp.unlink(missing_ok=True)


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


def _effective_damage(d: pd.DataFrame) -> pd.Series:
    """Health actually removed per hit (validated vs Leetify on 2 matches).

    - Normal hit: min(dmg_health, HP left before the hit).
    - Killing tick: all hits on the victim in that tick (e.g. shotgun pellets) together remove
      exactly the HP the victim had before the tick. dmg_health can be ~1 below the real HP loss
      because damage is fractional, so the last hit takes the remainder.
    """
    order = d.sort_values(["round_no", "victim_id", "tick", "victim_hp_after"],
                          ascending=[True, True, True, False], kind="mergesort")
    hp_after = order["victim_hp_after"].astype(int)
    prev_hp = order.groupby(["round_no", "victim_id"])["victim_hp_after"].shift(1).fillna(100).astype(int)
    eff = np.minimum(order["dmg_raw"].astype(int), prev_hp)

    grp = [order["round_no"], order["victim_id"], order["tick"]]
    hp_before_tick = prev_hp.groupby(grp).transform("first")
    is_last = ~order.duplicated(subset=["round_no", "victim_id", "tick"], keep="last")
    others = eff.groupby(grp).transform("sum") - eff
    kill_last = is_last & (hp_after <= 0)
    eff = eff.where(~kill_last, (hp_before_tick - others).clip(lower=0))
    return eff.astype(int).reindex(d.index)


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
    # Last round is open-ended. (Don't fillna(int64.max): it goes through float and overflows.)
    rounds["next_start_tick"] = rounds["start_tick"].shift(-1, fill_value=np.iinfo(np.int64).max).astype("int64")
    # Match end = cs_win_panel_match (fallback: last round_end). Events after it are "post-match"
    # (e.g. world suicides while the scoreboard is up).
    panel = _event(parser, "cs_win_panel_match")
    last_end = int(rounds["end_tick"].iloc[-1])
    panel_tick = int(panel["tick"].min()) if not panel.empty else -1
    rounds.attrs["match_end_tick"] = panel_tick if panel_tick >= last_end else last_end
    return rounds


def _assign_round(df: pd.DataFrame, rounds: pd.DataFrame, keep_post_match: bool = False) -> pd.DataFrame:
    """Attach round_no to events; drop events outside official rounds (warmup etc.).

    Post-match events are dropped unless keep_post_match, which keeps them flagged `post_match`.
    """
    if df.empty:
        df = df.copy()
        df["round_no"] = pd.Series(dtype="int64")
        if keep_post_match:
            df["post_match"] = pd.Series(dtype="bool")
        return df
    df = df.sort_values("tick").copy()
    df["tick"] = df["tick"].astype("int64")
    r = rounds[["round_no", "start_tick", "freeze_end_tick", "next_start_tick"]].sort_values("start_tick")
    out = pd.merge_asof(df, r, left_on="tick", right_on="start_tick", direction="backward")
    out = out[out["round_no"].notna() & (out["tick"] < out["next_start_tick"])]
    out["round_no"] = out["round_no"].astype("int64")
    post = out["tick"] > rounds.attrs["match_end_tick"]
    if keep_post_match:
        out["post_match"] = post
    else:
        out = out[~post]
    return out.drop(columns=["start_tick", "next_start_tick"])


# --------------------------------------------------------------------------- main

def parse_demo(
    path: str | Path,
    timeout: float | None = PARSE_TIMEOUT_SECONDS,
    max_bytes: int | None = MAX_DEMO_BYTES,
) -> ParsedDemo:
    """Parse a .dem (or .dem.bz2 / .dem.gz / .dem.zst) into event tables.

    timeout: seconds; parsing runs in a child process that is killed when it runs over
      (raises ParseTimeoutError). None = parse in this process, no limit.
    max_bytes: max size of the (decompressed) .dem (raises DemoTooLargeError). None = no limit.
    The temp .dem of a compressed demo is removed in every case.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    with _demo_file(path, max_bytes) as (dem_path, sha256):
        if not timeout:
            return _parse(dem_path, path, sha256)
        return _parse_in_child(dem_path, path, sha256, timeout)


def _child_main(dem_path: str, path: str, sha256: str, out: str) -> None:
    """Child process entry point: parse, then pickle the result (or the error) to `out`."""
    import pickle
    import traceback

    try:
        result = ("ok", _parse(Path(dem_path), Path(path), sha256))
    except BaseException as exc:  # noqa: BLE001 - report everything to the parent
        result = ("error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
    with open(out, "wb") as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)


def _parse_in_child(dem_path: Path, path: Path, sha256: str, timeout: float) -> ParsedDemo:
    import multiprocessing as mp
    import pickle

    fd, out_name = tempfile.mkstemp(suffix=".pkl", prefix="impactagent-")
    os.close(fd)
    out = Path(out_name)
    proc = mp.get_context("spawn").Process(
        target=_child_main, args=(str(dem_path), str(path), sha256, str(out)), daemon=True
    )
    try:
        proc.start()
        proc.join(timeout)
        if proc.is_alive():
            proc.kill()
            proc.join(10)
            raise ParseTimeoutError(f"{path.name}: parse took longer than {timeout:g}s")
        if proc.exitcode != 0 or out.stat().st_size == 0:
            raise RuntimeError(f"{path.name}: parser process exited with code {proc.exitcode}")
        with open(out, "rb") as f:
            status, payload = pickle.load(f)
        if status != "ok":
            raise RuntimeError(f"{path.name}: parse failed in child process: {payload}")
        return payload
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(10)
        out.unlink(missing_ok=True)


def _parse(dem_path: Path, path: Path, sha256: str) -> ParsedDemo:
    warnings: list[str] = []
    parser = DemoParser(str(dem_path))
    header = parser.parse_header() or {}
    map_name = header.get("map_name", "unknown")
    m = re.search(r"csgo_v(\d+)", header.get("game_directory", "") or "")
    client_build = int(m.group(1)) if m else None
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
    # Post-match deaths are kept (flagged) only because Leetify counts them in the
    # unused-utility denominator; every other metric must filter them out.
    k = _assign_round(k, rounds, keep_post_match=True)
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
    kills["post_match"] = k["post_match"].to_numpy(dtype=bool)
    # A player who leaves the server is killed by "world" in the same tick as player_disconnect.
    disc = _event(parser, "player_disconnect")
    left = set()
    if not disc.empty and "user_steamid" in disc:
        left = {(s, int(t) + dt) for s, t in zip(_sid(disc["user_steamid"]), disc["tick"]) if s for dt in (-1, 0, 1)}
    kills["by_disconnect"] = [
        bool(sui) and (v, int(t)) in left for v, t, sui in zip(kills["victim_id"], kills["tick"], kills["is_suicide"])
    ]

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
    damages["dmg_effective"] = _effective_damage(damages)
    damages = damages.sort_values(["round_no", "victim_id", "tick"], kind="mergesort").reset_index(drop=True)
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

    # ---- smokes (visibility): detonate .. expired
    sd, se = _event(parser, "smokegrenade_detonate"), _event(parser, "smokegrenade_expired")
    smokes = pd.DataFrame(columns=SMOKE_COLUMNS)
    if not sd.empty:
        sd = _assign_round(sd, rounds)
        sdet = pd.DataFrame({
            "round_no": sd["round_no"], "entity_id": sd["entityid"],
            "thrower_id": _sid(sd["user_steamid"]) if "user_steamid" in sd else None,
            "detonate_tick": sd["tick"], "x": sd["x"], "y": sd["y"], "z": sd["z"],
        })
        sexp = pd.DataFrame({"entity_id": se["entityid"], "tick": se["tick"]}) if not se.empty else pd.DataFrame()
        smokes = pair_smokes(sdet, sexp, tickrate)

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
    inv_cols = ["tick", "steam_id", "inventory", "active_weapon"]
    death_inventory = pd.DataFrame(columns=inv_cols)
    if death_ticks:
        # inventory is read one tick before death, while the player still holds it.
        # A grenade thrown just before death can still be listed (and active): metrics handle that.
        inv = pd.DataFrame(
            parser.parse_ticks(["inventory", "active_weapon_name"], ticks=[t - 1 for t in death_ticks])
        )
        if not inv.empty:
            inv["steam_id"] = _sid(inv["steamid"])
            inv["tick"] = inv["tick"] + 1
            inv["active_weapon"] = inv.get("active_weapon_name")
            # keep only the player(s) who died at that tick
            victims = kills[["tick", "victim_id"]].rename(columns={"victim_id": "steam_id"}).drop_duplicates()
            death_inventory = inv.merge(victims, on=["tick", "steam_id"])[inv_cols]

    rounds = rounds.drop(columns=["next_start_tick"])
    grenades.attrs["detonations"] = detonations
    trade_windows = build_trade_windows(
        parser, kills, damages, shots, player_rounds_side, tickrate, TRADE_WINDOW_SECONDS
    )
    shots, engagements, vis_backend = build_aim_tables(
        parser, shots, damages, kills, player_rounds_side, smokes, map_name, client_build, tickrate, warnings
    )
    return ParsedDemo(
        path=path,
        sha256=sha256,
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
        trade_windows=trade_windows,
        smokes=smokes,
        engagements=engagements,
        visibility_backend=vis_backend,
        client_build=client_build,
        warnings=warnings,
    )
