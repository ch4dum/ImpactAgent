"""Build wp_states (impact-spec §2.1) from parsed demos.

One row per "state": freeze end, then after every state-changing event — kill (suicide /
world / team kill included), bomb plant, defuse, explode, round end. Features are from the
T side's point of view. Derived data; no per-tick data is stored — equipment value is
sampled only at the state ticks (via `parse_ticks` on the exact ticks we need).

`trainable` marks which rows the WP model must predict. The rest have a WP fixed by rule
(§2.2 / round-end, defuse, explode, and rounds already decided by alive count).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from demoparser2 import DemoParser

from impactagent.constants import C4_TIMER_S, ROUND_TIME_S, SIDE_BY_TEAM_NUM
from impactagent.parse.demo import _demo_file, _sid, parse_demo

# Column order of the built table.
STATE_COLUMNS = [
    "match_id", "map", "round_no", "tick", "event_type", "event_ref",
    "t_alive", "ct_alive", "bomb_planted", "time_left_s", "equip_diff_k",
    "t_won", "trainable",
]

# Event priority within one tick (for a stable order when two kinds share a tick).
_EVENT_PRIO = {"freeze_end": 0, "kill": 1, "plant": 2, "defuse": 2, "explode": 2, "round_end": 3}

# Validation matches that must never be trained on (impact-spec §2.3). The three Leetify
# pairs are read from their truth JSON ("demo" field); the FACEIT match has no "demo" field.
FACEIT_VALIDATION_DEMO = "scripts/demos/1-8020514f-b9e8-41d1-8469-a4634cbdfeb3-1-1.dem.zst"

# A demo round-time / c4-timer read from server_cvar that differs from our constant by more
# than this (seconds) is reported as a warning.
TIMER_WARN_SECONDS = 1.0


def match_fingerprint(p) -> tuple:
    """(map, num_rounds, t_wins, ct_wins, frozenset(steam_id)) — identifies a match."""
    n = len(p.rounds)
    t = int((p.rounds["winner_side"] == "T").sum())
    return (p.map_name, n, t, n - t, frozenset(p.players["steam_id"]))


def infer_source(filename: str) -> str:
    """faceit / premier / other, from the demo filename convention (§2.3)."""
    name = Path(filename).name
    if name.startswith("1-") and name.endswith(".zst"):
        return "faceit"
    if name.endswith(".bz2"):
        return "premier"
    return "other"


def _iter_states(p, tickrate: int):
    """Yield one dict per state (everything except time_left_s and equip_diff_k)."""
    prs = p.player_rounds_side
    kills = p.kills
    if "post_match" in kills:
        kills = kills[~kills["post_match"]]

    for rno in sorted(p.rounds["round_no"]):
        r = p.rounds[p.rounds["round_no"] == rno].iloc[0]
        fe = int(r["freeze_end_tick"])
        end = int(r["end_tick"])
        has_plant = pd.notna(r["plant_tick"])
        plant_tick = int(r["plant_tick"]) if has_plant else None
        t_won = 1 if r["winner_side"] == "T" else 0

        rprs = prs[prs["round_no"] == rno]
        all_sids = set(rprs["steam_id"])
        # Side is per-round, not global: players swap sides at half-time, so a single
        # steam_id appears as both T and CT across the match. smearing one side over all
        # rounds (dict(zip(...)) would) flips equip_diff for every swapped player (bug).
        side_by_sid = dict(zip(rprs["steam_id"], rprs["side"]))
        init_t = int((rprs["side"] == "T").sum())
        init_ct = int((rprs["side"] == "CT").sum())

        # Only kills inside the round's live window [freeze_end, end] move the alive tally.
        # A kill before freeze_end belongs to the previous round's aftermath (or a pause /
        # timeout) and must not shrink whoever is alive now; a kill after `end` is post-round.
        rk = kills[(kills["round_no"] == rno) & (kills["tick"] >= fe) & (kills["tick"] <= end)]

        # Victims (and their side) per tick, preserving order.
        kill_by_tick: dict[int, list[tuple[object, str]]] = {}
        for tick, vid, vs in zip(rk["tick"], rk["victim_id"], rk["victim_side"]):
            kill_by_tick.setdefault(int(tick), []).append((vid, vs))

        rb = p.bomb[p.bomb["round_no"] == rno]

        events = [(fe, "freeze_end", "")]
        for t in sorted(kill_by_tick):
            events.append((t, "kill", json.dumps([str(v) for v, _ in kill_by_tick[t]])))
        for _, b in rb.iterrows():
            events.append((int(b["tick"]), str(b["type"]), str(b["steam_id"] or "")))
        events.append((end, "round_end", str(r["win_reason"])))
        events.sort(key=lambda e: (e[0], _EVENT_PRIO[e[1]]))

        planted = False
        # Alive tally from UNIQUE dead sids per side: a victim whose death fires twice in a
        # round (exit frag + a later duplicate) must not be subtracted twice (was -1 bug).
        dead_t_sids: set[object] = set()
        dead_ct_sids: set[object] = set()
        for tick, etype, ref in events:
            if etype == "kill":
                for vid, vs in kill_by_tick[tick]:
                    if pd.notna(vid):
                        if vs == "T":
                            dead_t_sids.add(vid)
                        elif vs == "CT":
                            dead_ct_sids.add(vid)
            if etype == "plant":
                planted = True
            yield {
                "round_no": rno,
                "tick": tick,
                "event_type": etype,
                "event_ref": ref,
                "t_alive": init_t - len(dead_t_sids),
                "ct_alive": init_ct - len(dead_ct_sids),
                "bomb_planted": 1 if planted else 0,
                "t_won": t_won,
                "alive_sids": all_sids - dead_t_sids - dead_ct_sids,
                "side_by_sid": side_by_sid,
                "freeze_end_tick": fe,
                "plant_tick": plant_tick,
            }


def _read_timers_and_equip(dem_path: Path, state_ticks: list[int]):
    """Open the demo a second time: read server_cvar (mp_roundtime/mp_c4timer) and sample
    equipment value only at the state ticks. -> (round_time_s, c4_timer_s, equip_df, warns)."""
    parser = DemoParser(str(dem_path))
    warns: list[str] = []

    cv = pd.DataFrame(parser.parse_event("server_cvar"))
    rt = c4 = None
    if not cv.empty:
        rt_rows = cv[cv["name"] == "mp_roundtime"]["value"]
        if len(rt_rows):
            rt = float(rt_rows.iloc[-1]) * 60.0  # server_cvar is minutes
        c4_rows = cv[cv["name"] == "mp_c4timer"]["value"]
        if len(c4_rows):
            c4 = float(c4_rows.iloc[-1])
    if rt is None:
        rt = ROUND_TIME_S
    elif abs(rt - ROUND_TIME_S) > TIMER_WARN_SECONDS:
        warns.append(f"mp_roundtime={rt:.1f}s differs from constant {ROUND_TIME_S}s")
    if c4 is None:
        c4 = C4_TIMER_S
    elif abs(c4 - C4_TIMER_S) > TIMER_WARN_SECONDS:
        warns.append(f"mp_c4timer={c4:.1f}s differs from constant {C4_TIMER_S}s")

    eq = pd.DataFrame(parser.parse_ticks(["team_num", "current_equip_value"], ticks=state_ticks))
    if eq.empty:
        eq = pd.DataFrame(columns=["tick", "steamid", "team_num", "current_equip_value"])
    eq["sid"] = _sid(eq["steamid"])
    eq = eq[eq["sid"].notna() & eq["team_num"].isin([2, 3])].copy()
    eq["side"] = eq["team_num"].map(SIDE_BY_TEAM_NUM)
    eq["value"] = eq.get("current_equip_value", 0).fillna(0).astype(float)
    return rt, c4, eq, warns


def build_wp_states(p) -> tuple[pd.DataFrame, dict]:
    """Build wp_states for one parsed demo. Returns (DataFrame, stats dict).

    `p` is a ParsedDemo (parse_demo(..., fast=True) is enough — trade/aim tables are unused).
    """
    states = list(_iter_states(p, p.tickrate))
    state_ticks = sorted({s["tick"] for s in states})

    dem_path = p.path
    with _demo_file(dem_path) as (plain, _sha):
        rt, c4, eq, timer_warns = _read_timers_and_equip(plain, state_ticks)
    eq_by_tick_sid = eq.set_index(["tick", "sid"])["value"].to_dict()

    rows = []
    n_neg_time = 0
    n_missing = 0
    n_extra = 0
    n_time_oob = 0          # time_left_s outside [0, limit + 1]
    n_alive_oob = 0         # t_alive / ct_alive outside [0, 5]
    n_equip_sign_viol = 0   # equip_diff_k moved against a kill's victim side
    freeze_alive_mismatch_rounds: set[int] = set()  # rounds whose freeze-end alive count
    #   disagrees between player_rounds_side and the tick snapshot (e.g. a bot present in
    #   one but not the other).
    prev = None
    for s in states:
        tick = s["tick"]
        bomb = bool(s["bomb_planted"])
        if bomb:
            time_left = c4 - (tick - s["plant_tick"]) / p.tickrate
            time_limit = c4
        else:
            time_left = rt - (tick - s["freeze_end_tick"]) / p.tickrate
            time_limit = rt
        if time_left < -1.0:
            n_neg_time += 1
        if time_left > time_limit + 1.0:
            n_time_oob += 1

        t_alive = s["t_alive"]
        ct_alive = s["ct_alive"]
        if not (0 <= t_alive <= 5 and 0 <= ct_alive <= 5):
            n_alive_oob += 1

        side_of = s["side_by_sid"]  # per-round side, not the global (swapped-side) mapping
        alive_sids = s["alive_sids"]
        t_sum = ct_sum = 0.0
        for sid in alive_sids:
            v = eq_by_tick_sid.get((tick, sid), 0.0)
            if side_of.get(sid) == "T":
                t_sum += v
            else:
                ct_sum += v
        equip_diff_k = (t_sum - ct_sum) / 1000.0

        # Assert: a kill of a T must not RAISE equip_diff (T side lost equipment), and a
        # kill of a CT must not LOWER it — relative to the previous state of this round.
        # (Weapon pick-ups in between can legitimately violate this; we count them.)
        if s["event_type"] == "kill" and prev is not None and prev["round_no"] == s["round_no"]:
            dt = t_alive - prev["t_alive"]
            dc = ct_alive - prev["ct_alive"]
            if dt < 0 and equip_diff_k > prev["equip_diff_k"]:
                n_equip_sign_viol += 1
            if dc < 0 and equip_diff_k < prev["equip_diff_k"]:
                n_equip_sign_viol += 1
        prev = {
            "round_no": s["round_no"], "t_alive": t_alive,
            "ct_alive": ct_alive, "equip_diff_k": equip_diff_k,
        }

        # Cross-check kills-based alive set vs who the tick data still lists alive.
        # missing = a survivor the tick data omits (their equip is under-counted as 0);
        # extra   = someone we count as dead still in the tick snapshot (the death tick).
        tick_alive = set(eq.loc[eq["tick"] == tick, "sid"])
        n_missing += len(alive_sids - tick_alive)
        n_extra += len(tick_alive - alive_sids)

        # At freeze_end the kills-based count must equal the tick snapshot count (bots
        # included). A difference means player_rounds_side and the tick snapshot disagree.
        if s["event_type"] == "freeze_end" and len(tick_alive) != t_alive + ct_alive:
            freeze_alive_mismatch_rounds.add(s["round_no"])

        rows.append(
            {
                "match_id": p.sha256,
                "map": p.map_name,
                "round_no": s["round_no"],
                "tick": tick,
                "event_type": s["event_type"],
                "event_ref": s["event_ref"],
                "t_alive": s["t_alive"],
                "ct_alive": s["ct_alive"],
                "bomb_planted": s["bomb_planted"],
                "time_left_s": time_left,
                "equip_diff_k": equip_diff_k,
                "t_won": s["t_won"],
                "trainable": _trainable(s["event_type"], s["t_alive"], s["ct_alive"], s["bomb_planted"]),
            }
        )

    df = pd.DataFrame(rows, columns=STATE_COLUMNS)
    df["round_no"] = df["round_no"].astype("int64")
    df["tick"] = df["tick"].astype("int64")
    df["t_alive"] = df["t_alive"].astype("int64")
    df["ct_alive"] = df["ct_alive"].astype("int64")
    df["bomb_planted"] = df["bomb_planted"].astype("int8")
    df["t_won"] = df["t_won"].astype("int8")
    df["trainable"] = df["trainable"].astype(bool)
    stats = {
        "timer_warns": timer_warns,
        "neg_time": n_neg_time,
        "time_oob": n_time_oob,
        "alive_oob": n_alive_oob,
        "equip_sign_viol": n_equip_sign_viol,
        "equip_alive_missing": n_missing,
        "equip_alive_extra": n_extra,
        "freeze_alive_mismatch_rounds": len(freeze_alive_mismatch_rounds),
    }
    return df, stats


def _trainable(event_type: str, t_alive: int, ct_alive: int, bomb_planted: int) -> bool:
    """False when the round outcome is already fixed by rule (impact-spec §2.2 / owner)."""
    if event_type in ("round_end", "defuse", "explode"):
        return False
    if ct_alive == 0:  # T win certain -> WP_T = 1
        return False
    if t_alive == 0 and not bomb_planted:  # T all dead, no bomb -> WP_T = 0
        return False
    return True  # freeze_end / kill / plant still undecided (or bomb down, CT may not defuse)


def validation_demo_paths(validation_dir: str | Path = "data/validation") -> list[Path]:
    """Demo paths of every validation pair, from the truth JSONs' "demo" field + FACEIT."""
    paths: list[Path] = []
    for jp in sorted(Path(validation_dir).glob("*.json")):
        try:
            demo = json.loads(jp.read_text(encoding="utf-8")).get("demo")
        except (json.JSONDecodeError, OSError):
            demo = None
        if demo and Path(demo).is_file():
            paths.append(Path(demo))
    faceit = Path(FACEIT_VALIDATION_DEMO)
    if faceit.is_file() and faceit not in paths:
        paths.append(faceit)
    return paths


def validation_fingerprints(validation_dir: str | Path = "data/validation") -> set[tuple]:
    """Fingerprints of every validation demo (parse once, cached in the returned set)."""
    fps: set[tuple] = set()
    for demo in validation_demo_paths(validation_dir):
        p = parse_demo(demo, fast=True)
        fps.add(match_fingerprint(p))
    return fps


_DEMO_SUFFIXES = (".dem", ".bz2", ".gz", ".zst")


def run_wp_states(
    demo_dir: str | Path,
    out_parquet: str | Path,
    manifest_path: str | Path,
    validation_dir: str | Path = "data/validation",
) -> int:
    """Build wp_states for every demo in `demo_dir`, skipping validation matches.

    Writes the concatenated states to `out_parquet` and a per-file `manifest.csv`. Prints a
    summary. Returns 0 on success, 1 if any demo failed to parse.
    """
    demo_dir = Path(demo_dir)
    vfps = validation_fingerprints(validation_dir)
    demo_files = sorted(f for f in demo_dir.iterdir() if f.is_file() and f.suffix.lower() in _DEMO_SUFFIXES)

    frames: list[pd.DataFrame] = []
    manifest_rows: list[dict] = []
    excluded_validation: list[str] = []
    failed: list[tuple[str, str]] = []
    total_neg_time = 0
    total_missing = 0
    total_extra = 0
    total_time_oob = 0
    total_alive_oob = 0
    total_sign_viol = 0
    total_freeze_mismatch_rounds = 0
    timer_warns_all: list[str] = []

    for f in demo_files:
        source = infer_source(f.name)
        try:
            p = parse_demo(f, fast=True)
        except Exception as exc:  # noqa: BLE001 - report the file and continue
            failed.append((f.name, str(exc)))
            manifest_rows.append(
                {"file": f.name, "map": "", "source": source, "rounds": "", "score": "",
                 "excluded_reason": "parse_failed"}
            )
            continue

        fp = match_fingerprint(p)
        n = len(p.rounds)
        score = f"{fp[2]}-{fp[3]}"
        if fp in vfps:
            excluded_validation.append(f.name)
            manifest_rows.append(
                {"file": f.name, "map": p.map_name, "source": source, "rounds": n,
                 "score": score, "excluded_reason": "validation"}
            )
            continue

        df, st = build_wp_states(p)
        frames.append(df)
        total_neg_time += st["neg_time"]
        total_missing += st["equip_alive_missing"]
        total_extra += st["equip_alive_extra"]
        total_time_oob += st["time_oob"]
        total_alive_oob += st["alive_oob"]
        total_sign_viol += st["equip_sign_viol"]
        total_freeze_mismatch_rounds += st["freeze_alive_mismatch_rounds"]
        timer_warns_all.extend(f"{f.name}: {w}" for w in st["timer_warns"])
        manifest_rows.append(
            {"file": f.name, "map": p.map_name, "source": source, "rounds": n,
             "score": score, "excluded_reason": ""}
        )

    manifest = pd.DataFrame(manifest_rows, columns=["file", "map", "source", "rounds", "score", "excluded_reason"])
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False)

    if frames:
        all_states = pd.concat(frames, ignore_index=True)
        out = Path(out_parquet)
        out.parent.mkdir(parents=True, exist_ok=True)
        all_states.to_parquet(out, index=False)
    else:
        all_states = pd.DataFrame(columns=STATE_COLUMNS)

    # ---- summary
    n_train = len(frames)
    # Rounds of USED matches only (excluded validation / parse-failed matches don't count).
    used = manifest[manifest["excluded_reason"] == ""]
    n_rounds = int(used["rounds"].astype(int).sum()) if len(used) else 0
    per_map = (
        manifest[manifest["excluded_reason"] == ""]
        .groupby("map").agg(matches=("file", "size"))
        .sort_values("matches", ascending=False)
    )
    trainable = int(all_states["trainable"].sum()) if len(all_states) else 0

    print(f"wp-states: {len(demo_files)} demos -> {out_parquet}")
    print(f"  matches used : {n_train} (excluded validation {len(excluded_validation)}, parse failed {len(failed)})")
    print(f"  rounds       : {n_rounds}")
    print(f"  state rows   : {len(all_states)} ({trainable} trainable, {len(all_states) - trainable} rule-fixed)")
    print("  matches per map (after validation cut):")
    for m, row in per_map.iterrows():
        print(f"    {m:<16} {int(row['matches']):>3}")
    if excluded_validation:
        print("  excluded (validation match):")
        for name in excluded_validation:
            print(f"    {name}")
    if failed:
        print("  parse failed:")
        for name, err in failed:
            print(f"    {name}: {err.splitlines()[0][:100]}")
    if timer_warns_all:
        print("  timer warnings:")
        for w in timer_warns_all:
            print(f"    {w}")
    print(f"  sanity: time_left_s < -1 rows = {total_neg_time}; "
          f"time_left_s out-of-range = {total_time_oob}; alive out-of-range = {total_alive_oob}; "
          f"equip-sign violations = {total_sign_viol}")
    print(f"          equip-alive cross-check missing={total_missing} extra={total_extra}; "
          f"freeze-end alive-mismatch rounds = {total_freeze_mismatch_rounds}")
    print(f"  manifest -> {manifest_path}")

    return 1 if failed else 0
