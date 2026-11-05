"""Round Win Share (RWS) per player — ESEA/FACEIT formula (impact-spec §4).

Winning team splits 100 points by share of effective damage done to enemies in the
round (team damage excluded). Bomb rounds give the planter/defuser a fixed 30 before the
remaining 70 is split by damage. Lost rounds are 0. The match value is the mean over the
rounds the player actually played, split by side (all / CT / T).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from impactagent.parse.demo import ParsedDemo

BOMB_BONUS = 30.0  # fixed points for planter (bomb_exploded) / defuser (bomb_defused)
BOMB_SHARE = 70.0  # points split by damage share after the bomb bonus


def _sequential_enemy_damage(damages: pd.DataFrame) -> pd.Series:
    """Effective damage per enemy hit, capping each hit at the victim's HP left before it.

    FACEIT RWS splits damage sequentially: when several hits land on a dying victim in one
    tick, each is capped at the HP still left in event order — NOT grouped the way the
    Leetify `dmg_effective` does ("killing tick = all hits together = HP before tick").
    Team/world damage still depletes the victim's HP in the same order (so an enemy hit
    after a team hit is capped lower), but only enemy hits are returned. Order is
    deterministic: (round, victim, tick), then the parser's original event order within a
    tick (a stable sort preserves it).
    """
    d = damages.sort_values(["round_no", "victim_id", "tick"], kind="mergesort").reset_index(drop=True)
    eff = np.zeros(len(d), dtype=float)
    hp: dict[tuple[int, str], float] = {}
    for i, row in d.iterrows():
        key = (int(row["round_no"]), row["victim_id"])
        rem = hp.get(key, 100.0)
        e = min(float(row["dmg_raw"]), rem)
        hp[key] = max(0.0, rem - e)
        if pd.notna(row["attacker_id"]) and not bool(row["is_team"]):
            eff[i] = e
    return pd.Series(eff, index=d.index)


def rws_metrics(p: ParsedDemo) -> pd.DataFrame:
    """-> DataFrame indexed by steam_id with columns rws (all), rws_ct, rws_t."""
    ids = p.players["steam_id"]
    out = pd.DataFrame(index=pd.Index(ids, name="steam_id"))

    # Sequential effective damage to enemies, summed per (round, player). Team damage is
    # excluded from the points but still depletes HP in the sequential order (impact-spec §4).
    seq = _sequential_enemy_damage(p.damages)
    dmg = p.damages.assign(dmg_sequential=seq.to_numpy())
    dmg_sum = dmg.groupby(["round_no", "attacker_id"])["dmg_sequential"].sum()

    # planter / defuser per round (first plant / defuse event in the round).
    planter: dict[int, str] = {}
    defuser: dict[int, str] = {}
    if not p.bomb.empty:
        for b in p.bomb.itertuples(index=False):
            if b.type == "plant" and b.round_no not in planter:
                planter[b.round_no] = b.steam_id
            elif b.type == "defuse" and b.round_no not in defuser:
                defuser[b.round_no] = b.steam_id

    pr = p.player_rounds_side[["round_no", "steam_id", "side"]]
    points: dict[tuple[int, str], float] = {}
    zero_dmg_rounds: list[int] = []

    for r in p.rounds.itertuples(index=False):
        rn = int(r.round_no)
        winner = r.winner_side
        if winner not in ("CT", "T"):
            continue
        side_players = pr[(pr["round_no"] == rn) & (pr["side"] == winner)]["steam_id"].tolist()
        if not side_players:
            continue
        d = {sid: float(dmg_sum.get((rn, sid), 0)) for sid in side_players}
        total = sum(d.values())

        if total <= 0:
            # Winning round with no damage (time out / enemies saved): even split, see report.
            zero_dmg_rounds.append(rn)
            share = 100.0 / len(side_players)
            for sid in side_players:
                points[(rn, sid)] = share
            continue

        bonus_pid: str | None = None
        if r.win_reason == "bomb_exploded":
            bonus_pid = planter.get(rn)
        elif r.win_reason == "bomb_defused":
            bonus_pid = defuser.get(rn)

        remaining = 100.0 if bonus_pid is None else BOMB_SHARE
        for sid in side_players:
            pts = remaining * d[sid] / total
            if sid == bonus_pid:
                pts += BOMB_BONUS
            points[(rn, sid)] = pts

    pts = pd.DataFrame(
        [(rn, sid, v) for (rn, sid), v in points.items()],
        columns=["round_no", "steam_id", "points"],
    )
    played = pr.merge(pts, on=["round_no", "steam_id"], how="left")
    played["points"] = played["points"].fillna(0.0)

    rws_all = played.groupby("steam_id")["points"].sum() / played.groupby("steam_id")["round_no"].count()
    ct = played[played["side"] == "CT"]
    t = played[played["side"] == "T"]
    rws_ct = ct.groupby("steam_id")["points"].sum() / ct.groupby("steam_id")["round_no"].count()
    rws_t = t.groupby("steam_id")["points"].sum() / t.groupby("steam_id")["round_no"].count()

    out["rws"] = rws_all.reindex(out.index).fillna(0.0)
    out["rws_ct"] = rws_ct.reindex(out.index).fillna(0.0)
    out["rws_t"] = rws_t.reindex(out.index).fillna(0.0)
    out.attrs["zero_dmg_rounds"] = zero_dmg_rounds
    return out
