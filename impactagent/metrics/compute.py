"""General + Utility metrics per player (one match).

Each metric returns value + numerator/denominator where it is a ratio,
matching the metric_values table in docs/design/data-model.md.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from impactagent.constants import (
    FIRE_DAMAGE_WEAPONS,
    GRENADE_ITEM_TYPES,
    GRENADE_PRICES,
    HE_DAMAGE_WEAPONS,
    MIN_BLIND_SECONDS,
    THROWN_GRENADE_GRACE_SECONDS,
    TRADE_ATTEMPT_AIM_DEG,
    TRADE_WINDOW_SECONDS,
)
from impactagent.parse.demo import ParsedDemo


HE_DMG_COL = "dmg_raw"
HE_TEAM_DMG_COL = "dmg_raw"


def _ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else float("nan")


# --------------------------------------------------------------------------- player_rounds

def _assists(p: ParsedDemo, flash: bool = False) -> pd.DataFrame:
    """Kills that give the assister an assist (validated on 2 matches, see spec).

    Counted on every death, including team kills, when the assister is an enemy of the victim;
    helping an enemy kill your own teammate is not an assist.
    flash=False: damage assists only (Leetify's Assists column; flash assists are not in it).
    flash=True: flash assists only (they DO count as the "A" in KAST).
    """
    side = p.player_rounds_side.set_index(["round_no", "steam_id"])["side"]
    is_flash = p.kills["flash_assist"].astype(bool)
    k = p.kills[p.kills["assister_id"].notna() & (is_flash if flash else ~is_flash)].copy()
    k["assister_side"] = [side.get((r, s)) for r, s in zip(k["round_no"], k["assister_id"])]
    return k[k["assister_side"] != k["victim_side"]]


def build_player_rounds(p: ParsedDemo) -> pd.DataFrame:
    """One row per player per round: K, D, A, damage, survived, traded, KAST."""
    pr = p.player_rounds_side.copy()
    kills = p.kills[~p.kills["is_team_kill"] & ~p.kills["is_suicide"]]
    all_deaths = p.kills
    dmg = p.damages[~p.damages["is_team"] & p.damages["attacker_id"].notna()]

    k = kills.groupby(["round_no", "attacker_id"]).size().rename("kills")
    d = all_deaths.groupby(["round_no", "victim_id"]).size().rename("deaths")
    a = _assists(p).groupby(["round_no", "assister_id"]).size().rename("assists")
    fa = _assists(p, flash=True).groupby(["round_no", "assister_id"]).size().rename("flash_assists")
    hs = kills[kills["headshot"].astype(bool)].groupby(["round_no", "attacker_id"]).size().rename("hs_kills")
    dm = dmg.groupby(["round_no", "attacker_id"])["dmg_effective"].sum().rename("damage")

    pr = pr.set_index(["round_no", "steam_id"])
    cols = ("kills", "deaths", "assists", "flash_assists", "hs_kills", "damage")
    for s in (k, d, a, fa, hs, dm):
        s.index = s.index.set_names(["round_no", "steam_id"])
        pr = pr.join(s)
    pr = pr.fillna({c: 0 for c in cols}).reset_index()
    for c in cols:
        pr[c] = pr[c].astype(int)
    pr["survived"] = pr["deaths"] == 0

    # traded: your killer was killed by your teammate within the trade window
    window = int(TRADE_WINDOW_SECONDS * p.tickrate)
    traded = set()
    for _, death in all_deaths.iterrows():
        if death["is_suicide"] or death["is_team_kill"]:
            continue
        later = kills[
            (kills["round_no"] == death["round_no"])
            & (kills["victim_id"] == death["attacker_id"])
            & (kills["tick"] > death["tick"])
            & (kills["tick"] <= death["tick"] + window)
        ]
        if not later.empty:
            traded.add((death["round_no"], death["victim_id"]))
    pr["traded"] = [(r, s) in traded for r, s in zip(pr["round_no"], pr["steam_id"])]
    # A in KAST = damage assist OR flash assist (mirage-65db631a, Boonrywaa r10).
    pr["kast"] = (pr["kills"] > 0) | (pr["assists"] > 0) | (pr["flash_assists"] > 0) | pr["survived"] | pr["traded"]
    return pr


# --------------------------------------------------------------------------- general

def general_metrics(p: ParsedDemo, pr: pd.DataFrame) -> pd.DataFrame:
    g = pr.groupby("steam_id")
    out = pd.DataFrame(
        {
            "rounds": g["round_no"].nunique(),
            "kills": g["kills"].sum(),
            "deaths": g["deaths"].sum(),
            "assists": g["assists"].sum(),
            "hs_kills": g["hs_kills"].sum(),
            "damage": g["damage"].sum(),
            "rounds_survived": g["survived"].sum(),
            "kast_rounds": g["kast"].sum(),
        }
    )
    for n in range(1, 6):
        out[f"multi{n}k"] = pr[pr["kills"] == n].groupby("steam_id").size().reindex(out.index).fillna(0).astype(int)
    out["kd"] = out["kills"] / out["deaths"].replace(0, np.nan)
    out["adr"] = out["damage"] / out["rounds"]
    out["kast"] = out["kast_rounds"] / out["rounds"]
    out["hs_kill_pct"] = out["hs_kills"] / out["kills"].replace(0, np.nan)
    out["rounds_survived_pct"] = out["rounds_survived"] / out["rounds"]

    # HLTV Rating 1.0 (public formula)
    kpr = out["kills"] / out["rounds"]
    spr = (out["rounds"] - out["deaths"]) / out["rounds"]
    rmk = (out["multi1k"] + 4 * out["multi2k"] + 9 * out["multi3k"] + 16 * out["multi4k"] + 25 * out["multi5k"]) / out["rounds"]
    out["hltv_rating"] = (kpr / 0.679 + 0.7 * spr / 0.317 + rmk / 1.277) / 2.7

    # Opening duels
    first = (
        p.kills[~p.kills["is_team_kill"] & ~p.kills["is_suicide"]]
        .sort_values("tick")
        .groupby("round_no")
        .head(1)
    )
    wins = first.groupby("attacker_id").size()
    losses = first.groupby("victim_id").size()
    out["opening_attempts"] = wins.reindex(out.index).fillna(0) + losses.reindex(out.index).fillna(0)
    out["opening_wins"] = wins.reindex(out.index).fillna(0)
    # Denominator = rounds in the MATCH, not rounds the player played (mirage-65db631a, J: 6/24).
    # ADR / KAST / HLTV keep rounds played.
    out["opening_attempt_pct"] = out["opening_attempts"] / len(p.rounds)
    out["opening_success_pct"] = out["opening_wins"] / out["opening_attempts"].replace(0, np.nan)
    return out


# --------------------------------------------------------------------------- utility

def _utility_value(inv, skip_one_of: str | None = None) -> int:
    """$ value of grenades in an inventory list, counting each grenade TYPE once.

    Leetify counts 2 flashbangs as one (mirage-65db631a: 7/7 cases). `skip_one_of` drops one
    item first (a grenade that was just thrown).
    """
    if inv is None or (isinstance(inv, float) and np.isnan(inv)):
        return 0
    items = [str(i).lower() for i in list(inv)]
    skip = skip_one_of.lower() if isinstance(skip_one_of, str) else None
    if skip in items:
        items.remove(skip)
    return sum(GRENADE_PRICES.get(name, 0) for name in set(items))


def _unused_utility(p: ParsedDemo, all_kills: pd.DataFrame) -> pd.Series:
    """Average $ of grenades held at death (calibrated on inferno-44a522c3, see spec).

    - A grenade thrown <= THROWN_GRENADE_GRACE_SECONDS before death that is still the active
      weapon is not counted.
    - Denominator = every death event incl. post-match ones (Leetify does this).
    """
    inv = p.death_inventory
    if inv.empty:
        return pd.Series(dtype=float)
    deaths = all_kills[["tick", "victim_id", "round_no"]].rename(columns={"victim_id": "steam_id"})
    inv = deaths.merge(inv, on=["tick", "steam_id"], how="left")
    grace = int(THROWN_GRENADE_GRACE_SECONDS * p.tickrate)
    throws = p.grenades

    def just_thrown(row) -> str | None:
        active = row.get("active_weapon")
        gtype = GRENADE_ITEM_TYPES.get(str(active).lower())
        if gtype is None:
            return None
        t = throws[
            (throws["thrower_id"] == row["steam_id"])
            & (throws["type"] == gtype)
            & (throws["throw_tick"] <= row["tick"])
            & (throws["throw_tick"] >= row["tick"] - grace)
        ]
        return active if not t.empty else None

    inv["value"] = [_utility_value(r["inventory"], just_thrown(r)) for _, r in inv.iterrows()]
    return inv.groupby("steam_id")["value"].mean()


def utility_metrics(p: ParsedDemo, all_kills: pd.DataFrame | None = None) -> pd.DataFrame:
    ids = p.players["steam_id"]
    out = pd.DataFrame(index=pd.Index(ids, name="steam_id"))

    thrown = p.grenades.groupby(["thrower_id", "type"]).size().unstack(fill_value=0)
    for t in ("flash", "smoke", "he", "molotov"):
        out[f"{t}_thrown"] = thrown[t].reindex(out.index).fillna(0).astype(int) if t in thrown else 0

    bl = p.blinds[p.blinds["thrower_id"].notna()]
    # Blinds on players who are already dead don't count (player_blind still fires for them).
    death_tick = p.kills.groupby(["round_no", "victim_id"])["tick"].min()
    dead_at = pd.Series([death_tick.get((r, v)) for r, v in zip(bl["round_no"], bl["victim_id"])], index=bl.index)
    bl = bl[~(dead_at.notna() & (dead_at < bl["tick"]))]
    long = bl[bl["duration"] > MIN_BLIND_SECONDS]
    enemy = long[~long["is_teammate"]]
    friend = long[long["is_teammate"] | (long["thrower_id"] == long["victim_id"])]
    enemy_any = bl[~bl["is_teammate"]]
    out["enemies_flashed"] = enemy.groupby("thrower_id").size().reindex(out.index).fillna(0).astype(int)
    out["friends_flashed"] = friend.groupby("thrower_id").size().reindex(out.index).fillna(0).astype(int)
    out["enemies_flashed_per_flash"] = out["enemies_flashed"] / out["flash_thrown"].replace(0, np.nan)
    out["friends_flashed_per_flash"] = out["friends_flashed"] / out["flash_thrown"].replace(0, np.nan)
    out["enemy_blind_seconds_total"] = enemy.groupby("thrower_id")["duration"].sum().reindex(out.index).fillna(0)

    # Blind duration: per flash, longest enemy blind; averaged over flashes that blinded >=1 live
    # enemy for ANY duration (no 1.1s cut here, and no cut at the victim's death).
    key = "entity_id" if enemy_any["entity_id"].notna().any() else "tick"
    per_flash = enemy_any.groupby(["thrower_id", key])["duration"].max()
    out["flash_blind_duration_avg"] = per_flash.groupby(level=0).mean().reindex(out.index)

    # Flash assists (from kill events)
    k = p.kills[~p.kills["is_team_kill"] & ~p.kills["is_suicide"]]
    fa = k[k["flash_assist"].astype(bool) & k["assister_id"].notna()]
    out["flash_assists"] = fa.groupby("assister_id").size().reindex(out.index).fillna(0).astype(int)

    # Flashbangs leading to kills: enemy killed while still blind from your flash (>1.1s blinds)
    tr = p.tickrate
    leading = []
    for _, kill in k.iterrows():
        b = enemy[
            (enemy["victim_id"] == kill["victim_id"])
            & (enemy["round_no"] == kill["round_no"])
            & (enemy["tick"] <= kill["tick"])
            & (enemy["tick"] + enemy["duration"] * tr >= kill["tick"])
        ]
        if not b.empty:
            leading.append(b.sort_values("tick").iloc[-1]["thrower_id"])
    out["flashes_leading_to_kill"] = pd.Series(leading, dtype="object").value_counts().reindex(out.index).fillna(0).astype(int)
    # Per KILL (one flash can count several times), by anyone incl. the thrower, / flashes thrown.
    out["flash_assist_pct"] = out["flashes_leading_to_kill"] / out["flash_thrown"].replace(0, np.nan)

    # HE / fire damage
    dmg = p.damages[p.damages["attacker_id"].notna()]
    he = dmg[dmg["weapon"].isin(HE_DAMAGE_WEAPONS)]
    fire = dmg[dmg["weapon"].isin(FIRE_DAMAGE_WEAPONS)]
    # HE damage uses raw dmg_health, NOT capped at remaining HP (mirage-65db631a).
    out["he_damage_enemies"] = he[~he["is_team"]].groupby("attacker_id")[HE_DMG_COL].sum().reindex(out.index).fillna(0)
    # Team HE damage includes damage to yourself (inferno-44a522c3).
    out["he_damage_team"] = he[he["is_team"]].groupby("attacker_id")[HE_TEAM_DMG_COL].sum().reindex(out.index).fillna(0)
    out["he_damage_per_he"] = out["he_damage_enemies"] / out["he_thrown"].replace(0, np.nan)
    out["he_team_damage_per_he"] = out["he_damage_team"] / out["he_thrown"].replace(0, np.nan)
    out["molotov_damage_enemies"] = fire[~fire["is_team"]].groupby("attacker_id")["dmg_effective"].sum().reindex(out.index).fillna(0)

    out["unused_utility_on_death_avg"] = _unused_utility(p, all_kills if all_kills is not None else p.kills).reindex(out.index)
    return out


# --------------------------------------------------------------------------- trades

def trade_flags(tw: pd.DataFrame) -> pd.DataFrame:
    """Add had_opportunity / attempted to trade_windows (spec §3; opportunity + attempt are
    HYPOTHESES, succeeded is validated)."""
    tw = tw.copy()
    tw["attempted"] = tw["damaged_killer"] | (tw["fired"] & (tw["min_aim_angle_spotted"] < TRADE_ATTEMPT_AIM_DEG))
    tw["had_opportunity"] = tw["attempted"] | tw["teammate_spotted_killer"] | tw["killer_spotted_teammate"]
    return tw


def trade_metrics(p: ParsedDemo) -> pd.DataFrame:
    out = pd.DataFrame(index=pd.Index(p.players["steam_id"], name="steam_id"))
    tw = p.trade_windows
    if tw is None or tw.empty:
        for c in ("trade_kill_opportunities", "trade_kill_attempts", "trade_kills_succeed",
                  "traded_death_opportunities", "traded_death_attempts", "traded_deaths_succeed"):
            out[c] = 0
        out["opening_traded_pct"] = np.nan
        return out
    tw = trade_flags(tw)
    per_death = tw.groupby(["dead_id", "death_tick"])[["had_opportunity", "attempted", "succeeded"]].any().reset_index()
    for flag, tk_col, td_col in [("had_opportunity", "trade_kill_opportunities", "traded_death_opportunities"),
                                 ("attempted", "trade_kill_attempts", "traded_death_attempts"),
                                 ("succeeded", "trade_kills_succeed", "traded_deaths_succeed")]:
        out[tk_col] = tw[tw[flag]].groupby("teammate_id").size().reindex(out.index).fillna(0).astype(int)
        out[td_col] = per_death[per_death[flag]].groupby("dead_id").size().reindex(out.index).fillna(0).astype(int)

    # Opening traded % = opening deaths that were traded / opening deaths.
    first = (
        p.kills[~p.kills["is_team_kill"] & ~p.kills["is_suicide"]].sort_values("tick").groupby("round_no").head(1)
    )
    traded = set(zip(per_death.loc[per_death["succeeded"], "dead_id"], per_death.loc[per_death["succeeded"], "death_tick"]))
    first = first.assign(traded=[(v, t) in traded for v, t in zip(first["victim_id"], first["tick"])])
    g = first.groupby("victim_id")["traded"]
    out["opening_deaths"] = g.size().reindex(out.index).fillna(0).astype(int)
    out["opening_deaths_traded"] = g.sum().reindex(out.index).fillna(0).astype(int)
    out["opening_traded_pct"] = out["opening_deaths_traded"] / out["opening_deaths"].replace(0, np.nan)
    return out


# --------------------------------------------------------------------------- clutches

def build_clutches(p: ParsedDemo) -> pd.DataFrame:
    """One row per clutch (data-model `clutches`).

    A clutch starts when a death leaves a player as the last one alive on his side with
    vs_n >= 1 enemies alive. kills = his kills from then until the end of the round.
    outcome: won (his side won) / saved (lost but he survived) / lost.
    Every death counts for "alive" (team kills, suicides, world), post-match deaths do not.
    """
    cols = ["round_no", "steam_id", "side", "vs_n", "start_tick", "kills", "outcome"]
    k = p.kills
    if "post_match" in k:
        k = k[~k["post_match"]]
    k = k.sort_values("tick", kind="mergesort")
    rounds = p.rounds.set_index("round_no")
    rows = []
    for rn, roster in p.player_rounds_side.groupby("round_no"):
        alive = {s: set(g["steam_id"]) for s, g in roster.groupby("side")}
        if set(alive) != {"CT", "T"}:
            continue
        started: set[str] = set()
        rk = k[k["round_no"] == rn]
        for d in rk.itertuples(index=False):
            for s in alive:
                alive[s].discard(d.victim_id)
            for s, other in (("CT", "T"), ("T", "CT")):
                if len(alive[s]) == 1 and alive[other]:
                    (sid,) = alive[s]
                    if sid not in started:
                        started.add(sid)
                        rows.append({"round_no": rn, "steam_id": sid, "side": s, "vs_n": len(alive[other]),
                                     "start_tick": int(d.tick)})
        for r in rows:
            if r["round_no"] != rn:
                continue
            after = rk[rk["tick"] > r["start_tick"]]
            r["kills"] = int(((after["attacker_id"] == r["steam_id"]) & ~after["is_team_kill"] & ~after["is_suicide"]).sum())
            died = bool((rk["victim_id"] == r["steam_id"]).any())
            won = rounds.at[rn, "winner_side"] == r["side"]
            r["outcome"] = "won" if won else ("lost" if died else "saved")
    return pd.DataFrame(rows, columns=cols)


def clutch_metrics(p: ParsedDemo, clutches: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=pd.Index(p.players["steam_id"], name="steam_id"))
    g = clutches.groupby("steam_id")
    out["clutches"] = g.size().reindex(out.index).fillna(0).astype(int)
    for o in ("won", "lost", "saved"):
        out[f"clutches_{o}"] = clutches[clutches["outcome"] == o].groupby("steam_id").size().reindex(out.index).fillna(0).astype(int)
    out["clutch_kills"] = g["kills"].sum().reindex(out.index).fillna(0).astype(int)
    return out


# --------------------------------------------------------------------------- all

def compute_match_metrics(p: ParsedDemo) -> pd.DataFrame:
    all_kills = p.kills
    if "post_match" in all_kills:  # post-match deaths only feed the unused-utility denominator
        p = replace(p, kills=all_kills[~all_kills["post_match"]].reset_index(drop=True))
    pr = build_player_rounds(p)
    gen = general_metrics(p, pr)
    util = utility_metrics(p, all_kills)
    trades = trade_metrics(p)
    clutch = clutch_metrics(p, build_clutches(p))
    names = p.players.set_index("steam_id")[["name", "team"]]
    return names.join(gen).join(util).join(trades).join(clutch)
