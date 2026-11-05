"""Impact credit assignment (impact-spec §3): wp_states + WP model -> rating_events.

For every state e after freeze end (wp_states order):
  wp_pre(e)    = WP of the state BEFORE e, with the clock moved to e's tick
  delta_time   = wp_pre(e) - wp_after(previous)  -> `time` rows (survivors share it; none: no player)
  delta_event  = wp_after(e) - wp_pre(e)         -> split between players (§3.2)
  round end    : delta = outcome - wp_after(last event) (no separate time part)

Units: `rating_events.delta` is a FRACTION of a round win (T-side WP is in [0, 1]); the
row's delta is from the row's own side (T rows +D, CT rows -D for a T-side change D).
The only ×100 (to % per round) is `PCT`, applied in `impact_metrics` and the CLI tables.

Per round the rows are zero-sum between T and CT, and the T rows sum to t_won - wp_start
(`check_invariants`). Rows with steam_id = null are `time` (only with `time_credit: none`;
the default `survivors` gives them to the players alive), `disconnect` (a death by leaving
the server is nobody's play) and bot rows (`is_bot`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from impactagent.constants import TRADE_WINDOW_SECONDS
from impactagent.metrics.compute import build_clutches
from impactagent.metrics.rws import _sequential_enemy_damage
from impactagent.ratings.wp_model import load_model, predict_wp
from impactagent.ratings.wp_states import _trainable, build_wp_states

CFG_PATH = Path(__file__).with_name("credit.yaml")
PCT = 100.0  # fraction -> % per round; used only by impact_metrics and the CLI
TOL = 1e-9
# credit.yaml `time_credit`: survivors (default) = each side's players alive before the event
# share delta_time equally (whole team if nobody is alive), category `time`; none = time rows
# have no player (steam_id null).
TIME_CREDIT_MODES = ("none", "survivors")

CATEGORIES = (
    "opening_duel", "mid_round_kd", "clutch", "afterplant", "retake",
    "damage_assist", "flash_assist", "traded", "enemy_saving", "time", "disconnect",
)

COLUMNS = [
    "match_id", "round_no", "seq", "sub", "tick", "event_type", "event_ref", "part",
    "steam_id", "is_bot", "side", "category", "delta", "wp_pre", "wp_after",
]


def load_config(path: str | Path = CFG_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _sgn(side: str) -> float:
    return 1.0 if side == "T" else -1.0


def _sid_or_none(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    s = str(v)
    return None if s in ("", "nan", "None", "<NA>") else s


def _state_wps(states: pd.DataFrame, model: dict, tickrate: int) -> tuple[np.ndarray, np.ndarray]:
    """(wp_after, wp_pre) per state row (T side). wp_pre of freeze_end = its wp_after."""
    st = states.reset_index(drop=True)
    wp_after = predict_wp(st, model=model).to_numpy().copy()

    prev = st.shift(1)
    first = (st["event_type"] == "freeze_end") | (st["round_no"] != prev["round_no"])
    pre = st.copy()
    for c in ("t_alive", "ct_alive", "bomb_planted", "equip_diff_k"):
        pre[c] = np.where(first, st[c], prev[c])
    pre["time_left_s"] = np.where(
        first, st["time_left_s"], prev["time_left_s"] - (st["tick"] - prev["tick"]) / tickrate
    )
    prev_et = prev["event_type"].fillna("kill")
    pre["event_type"] = np.where(prev_et.isin(["defuse", "explode"]), prev_et, "kill")
    pre["trainable"] = [
        _trainable(et, int(t), int(c), int(b))
        for et, t, c, b in zip(pre["event_type"], pre["t_alive"], pre["ct_alive"], pre["bomb_planted"])
    ]
    wp_pre = predict_wp(pre, model=model).to_numpy().copy()
    wp_pre[first.to_numpy()] = wp_after[first.to_numpy()]

    # Once a defuse / explode has decided the round, every later state keeps that WP
    # (a kill after the explosion must not move WP back to a model value).
    decided: float | None = None
    for i in range(len(st)):
        if first.iat[i]:
            decided = None
        et = st.at[i, "event_type"]
        if decided is not None and et != "round_end":
            wp_pre[i] = wp_after[i] = decided
        if et in ("defuse", "explode"):
            decided = wp_after[i]
    return wp_after, wp_pre


def build_rating_events(p, states: pd.DataFrame | None = None, model: dict | None = None,
                        cfg: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """-> (rating_events, rounds) where rounds = [round_no, wp_start, t_won] per round.

    `p` is a ParsedDemo; traded-death credit needs `p.trade_windows` (full parse, not fast).
    """
    cfg = cfg or load_config()
    model = model or load_model()
    if states is None:
        states, _ = build_wp_states(p)
    states = states.reset_index(drop=True)
    wp_after, wp_pre = _state_wps(states, model, p.tickrate)
    split = cfg["kill_split"]
    time_mode = cfg.get("time_credit", "survivors")
    if time_mode not in TIME_CREDIT_MODES:
        raise ValueError(f"time_credit must be one of {TIME_CREDIT_MODES}, got {time_mode!r}")

    kills = p.kills
    if "post_match" in kills:
        kills = kills[~kills["post_match"]]
    kills = kills.sort_values("tick", kind="mergesort")
    # Opening kill per round: same rule as general_metrics (first kill, no team kill / suicide).
    opening_idx = set(
        kills[~kills["is_team_kill"] & ~kills["is_suicide"]].groupby("round_no").head(1).index
    )

    d = p.damages
    order = d.sort_values(["round_no", "victim_id", "tick"], kind="mergesort").index
    if not (order == d.index).all():  # rws._sequential_enemy_damage returns sorted order
        d = d.loc[order].reset_index(drop=True)
    d = d.assign(dmg_seq=_sequential_enemy_damage(d).to_numpy())
    d = d[(d["dmg_seq"] > 0) & d["attacker_id"].notna()]

    clutches = build_clutches(p)
    clutch_start = {(int(r.round_no), r.steam_id): int(r.start_tick) for r in clutches.itertuples(index=False)}

    tw = p.trade_windows
    if tw is not None and not tw.empty:
        tw = tw[tw["succeeded"]]
    trade_w = int(TRADE_WINDOW_SECONDS * p.tickrate)

    planter: dict[int, str | None] = {}
    if not p.bomb.empty:
        for b in p.bomb[p.bomb["type"] == "plant"].itertuples(index=False):
            planter.setdefault(int(b.round_no), _sid_or_none(b.steam_id))

    rounds_tab = p.rounds.set_index("round_no")
    prs = p.player_rounds_side
    rows: list[dict] = []
    round_rows: list[dict] = []
    match_id = p.sha256

    for rno, idx in states.groupby("round_no", sort=True).groups.items():
        idx = list(idx)
        rno = int(rno)
        r = rounds_tab.loc[rno]
        fe, end = int(r["freeze_end_tick"]), int(r["end_tick"])
        roster = prs[prs["round_no"] == rno]
        side_of = dict(zip(roster["steam_id"], roster["side"]))
        team = {s: [sid for sid, sd in side_of.items() if sd == s] for s in ("T", "CT")}
        alive = set(side_of)
        rk = kills[(kills["round_no"] == rno) & (kills["tick"] >= fe) & (kills["tick"] <= end)]
        kills_at = {int(t): g for t, g in rk.groupby("tick", sort=False)}
        rd = d[d["round_no"] == rno]
        t_won = int(states.at[idx[0], "t_won"])
        round_rows.append({"round_no": rno, "wp_start": float(wp_after[idx[0]]), "t_won": t_won})

        def cat(sid, side, tick, planted) -> str:
            st_ = clutch_start.get((rno, sid))
            if st_ is not None and tick >= st_:
                return "clutch"
            if planted:
                return "afterplant" if side == "T" else "retake"
            return "mid_round_kd"

        def receivers(side) -> list[str]:
            live = [s for s in team[side] if s in alive]
            return live or team[side]

        for j in range(1, len(idx)):
            i = idx[j]
            s = states.loc[i]
            seq, tick, et = j, int(s["tick"]), s["event_type"]
            planted_before = bool(states.at[idx[j - 1], "bomb_planted"])
            base = {"match_id": match_id, "round_no": rno, "seq": seq, "tick": tick,
                    "event_type": et, "event_ref": s["event_ref"],
                    "wp_pre": float(wp_pre[i]), "wp_after": float(wp_after[i])}

            def emit(part, sid, side, category, delta, sub=0, is_bot=False):
                rows.append({**base, "sub": sub, "part": part, "steam_id": sid, "is_bot": is_bot,
                             "side": side, "category": category, "delta": float(delta)})

            def null_pair(part, category, D, sub=0):
                emit(part, None, "T", category, D, sub)
                emit(part, None, "CT", category, -D, sub)

            if et == "round_end":
                base["wp_pre"] = float(wp_after[idx[j - 1]])
                D = t_won - float(wp_after[idx[j - 1]])
                if D != 0.0:
                    for side, sg in (("T", 1.0), ("CT", -1.0)):
                        rec = receivers(side)
                        for sid in rec:
                            emit("round_end", sid, side, "enemy_saving", sg * D / len(rec))
                continue

            Dt = float(wp_pre[i]) - float(wp_after[idx[j - 1]])
            if Dt != 0.0:
                if time_mode == "survivors":
                    # survivors before e (else the whole team) share the clock's ΔWP
                    for side, sg in (("T", 1.0), ("CT", -1.0)):
                        rec = receivers(side)
                        for sid in rec:
                            emit("time", sid, side, "time", sg * Dt / len(rec))
                else:
                    null_pair("time", "time", Dt)
            D = float(wp_after[i]) - float(wp_pre[i])

            if et == "kill":
                ks = kills_at.get(tick)
                if ks is None or ks.empty:
                    continue
                for v in ks["victim_id"]:
                    alive.discard(v)
                Dk = D / len(ks)
                for sub, (kidx, k) in enumerate(ks.iterrows()):
                    vic = _sid_or_none(k["victim_id"])
                    vs = k["victim_side"]
                    v_bot = vic is None
                    if bool(k.get("by_disconnect", False)):
                        null_pair("disconnect", "disconnect", Dk, sub)
                        continue
                    if bool(k["is_suicide"]) or bool(k["is_team_kill"]):
                        vd = Dk * _sgn(vs)
                        emit("death", vic, vs, cat(vic, vs, tick, planted_before), vd, sub, v_bot)
                        opp = "CT" if vs == "T" else "T"
                        rec = receivers(opp)
                        for sid in rec:
                            emit("opponent_split", sid, opp, cat(sid, opp, tick, planted_before),
                                 -vd / len(rec), sub)
                        continue
                    S = k["attacker_side"]
                    DS = Dk * _sgn(S)
                    att = _sid_or_none(k["attacker_id"])
                    opening = kidx in opening_idx
                    att_cat = "opening_duel" if opening else cat(att, S, tick, planted_before)
                    vic_cat = "opening_duel" if opening else cat(vic, vs, tick, planted_before)

                    parts: list[tuple[str, str, str, float]] = [("kill", att, att_cat, 1.0)]
                    if vic is not None:
                        vdm = rd[(rd["victim_id"] == vic) & (rd["tick"] <= tick)
                                 & (rd["attacker_side"] == S) & ~rd["is_team"]]
                        by = vdm.groupby("attacker_id")["dmg_seq"].sum()
                    else:
                        by = pd.Series(dtype=float)
                    dmg_parts = [(sid, float(x) / float(by.sum())) for sid, x in by.items()] if by.sum() > 0 else []
                    fl = _sid_or_none(k["assister_id"]) if bool(k["flash_assist"]) else None
                    if fl is not None and (side_of.get(fl) != S or fl == att):
                        fl = None
                    traded: list[str] = []
                    if tw is not None and not tw.empty and att is not None and vic is not None:
                        m = tw[(tw["round_no"] == rno) & (tw["teammate_id"] == att) & (tw["killer_id"] == vic)
                               & (tw["death_tick"] < tick) & (tick - tw["death_tick"] <= trade_w)]
                        traded = sorted(set(m["dead_id"]))

                    w = {"kill": split["kill"]}
                    if dmg_parts:
                        w["damage"] = split["damage"]
                    if fl is not None:
                        w["flash_assist"] = split["flash_assist"]
                    if traded:
                        w["traded_death"] = split["traded_death"]
                    tot = sum(w.values())
                    emit("kill", att, S, att_cat, DS * w["kill"] / tot, sub, att is None)
                    for sid, sh in dmg_parts:
                        c = att_cat if sid == att else "damage_assist"
                        emit("damage", sid, S, c, DS * w["damage"] / tot * sh, sub)
                    if fl is not None:
                        emit("flash_assist", fl, S, "flash_assist", DS * w["flash_assist"] / tot, sub)
                    for sid in traded:
                        emit("traded_death", sid, S, "traded", DS * w["traded_death"] / tot / len(traded), sub)
                    emit("death", vic, vs, vic_cat, -DS, sub, v_bot)

            elif et in ("plant", "explode"):
                # planter gets all of D; surviving CTs (else the whole CT team) share -D
                sid = _sid_or_none(s["event_ref"]) if et == "plant" else planter.get(rno)
                emit(et, sid, "T", "afterplant", D, 0, sid is None)
                rec = receivers("CT")
                for ct_sid in rec:
                    emit("opponent_split", ct_sid, "CT", "retake", -D / len(rec))
            elif et == "defuse":
                sid = _sid_or_none(s["event_ref"])
                emit("defuse", sid, "CT", "retake", -D, 0, sid is None)
                rec = receivers("T")
                for t_sid in rec:
                    emit("opponent_split", t_sid, "T", "afterplant", D / len(rec))

    ev = pd.DataFrame(rows, columns=COLUMNS)
    ev = ev.astype({"round_no": "int64", "seq": "int32", "sub": "int8", "tick": "int64",
                    "is_bot": bool, "delta": "float64", "wp_pre": "float64", "wp_after": "float64"})
    ev["steam_id"] = ev["steam_id"].astype("string")
    return ev, pd.DataFrame(round_rows, columns=["round_no", "wp_start", "t_won"])


def check_invariants(events: pd.DataFrame, rounds: pd.DataFrame, tol: float = TOL) -> list[str]:
    """Per round: (a) Σ T rows = t_won - wp_start, (b) Σ T + Σ CT = 0, (c) players + bots +
    time + disconnect partition (a); per state: Σ T rows = wp_after - wp_pre. -> problems."""
    probs: list[str] = []
    null_ok = events["part"].isin(["time", "disconnect"]) | events["is_bot"]
    bad_null = events[events["steam_id"].isna() & ~null_ok]
    if len(bad_null):
        probs.append(f"{len(bad_null)} rows with null steam_id outside time/disconnect/bot")
    for r in rounds.itertuples(index=False):
        e = events[events["round_no"] == r.round_no]
        t = e[e["side"] == "T"]
        a = t["delta"].sum()
        want = r.t_won - r.wp_start
        if abs(a - want) > tol:
            probs.append(f"r{r.round_no} (a) Σ T = {a:.12f} != t_won - wp_start = {want:.12f}")
        b = a + e.loc[e["side"] == "CT", "delta"].sum()
        if abs(b) > tol:
            probs.append(f"r{r.round_no} (b) Σ T + Σ CT = {b:.3e}")
        pl = t.loc[t["steam_id"].notna() | t["is_bot"], "delta"].sum()
        tm = t.loc[t["steam_id"].isna() & ~t["is_bot"], "delta"].sum()
        if abs(pl + tm - want) > tol:
            probs.append(f"r{r.round_no} (c) players {pl:.6f} + time/disconnect {tm:.6f} != {want:.6f}")
        for (seq, part_is_time), g in t.groupby([t["seq"], t["part"] == "time"]):
            if part_is_time:
                continue
            got = g["delta"].sum()
            exp = g["wp_after"].iat[0] - g["wp_pre"].iat[0]
            if abs(got - exp) > tol:
                probs.append(f"r{r.round_no} seq {seq}: Σ T rows {got:.6f} != ΔWP {exp:.6f}")
    return probs


def player_round_ratings(events: pd.DataFrame, p) -> pd.DataFrame:
    """player_rounds.rating: Σ delta (fraction) per (round, player); 0 for rounds with no row."""
    pr = p.player_rounds_side[["round_no", "steam_id", "side"]].copy()
    e = events[events["steam_id"].notna()]
    s = e.groupby(["round_no", "steam_id"])["delta"].sum().rename("rating").reset_index()
    s["steam_id"] = s["steam_id"].astype(object)
    out = pr.merge(s, on=["round_no", "steam_id"], how="left")
    out["rating"] = out["rating"].fillna(0.0)
    out.insert(0, "match_id", p.sha256)
    return out


def impact_metrics(p, events: pd.DataFrame | None = None) -> pd.DataFrame:
    """-> DataFrame indexed by steam_id: impact, impact_ct, impact_t in % per round played
    (the one ×100, `PCT`). Across matches aggregate Σ rating / Σ rounds, never mean of means."""
    if events is None:
        events, _ = build_rating_events(p)
    prr = player_round_ratings(events, p)
    out = pd.DataFrame(index=pd.Index(p.players["steam_id"], name="steam_id"))
    for col, sub in (("impact", prr), ("impact_ct", prr[prr["side"] == "CT"]), ("impact_t", prr[prr["side"] == "T"])):
        out[col] = (sub.groupby("steam_id")["rating"].mean() * PCT).reindex(out.index)
    return out
