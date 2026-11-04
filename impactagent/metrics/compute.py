"""General + Utility metrics per player (one match).

Each metric returns value + numerator/denominator where it is a ratio,
matching the metric_values table in docs/design/data-model.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from impactagent.constants import (
    FIRE_DAMAGE_WEAPONS,
    GRENADE_PRICES,
    HE_DAMAGE_WEAPONS,
    MIN_BLIND_SECONDS,
    TRADE_WINDOW_SECONDS,
)
from impactagent.parse.demo import ParsedDemo


def _ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else float("nan")


# --------------------------------------------------------------------------- player_rounds

def build_player_rounds(p: ParsedDemo) -> pd.DataFrame:
    """One row per player per round: K, D, A, damage, survived, traded, KAST."""
    pr = p.player_rounds_side.copy()
    kills = p.kills[~p.kills["is_team_kill"] & ~p.kills["is_suicide"]]
    all_deaths = p.kills
    dmg = p.damages[~p.damages["is_team"] & p.damages["attacker_id"].notna()]

    k = kills.groupby(["round_no", "attacker_id"]).size().rename("kills")
    d = all_deaths.groupby(["round_no", "victim_id"]).size().rename("deaths")
    a = kills[kills["assister_id"].notna()].groupby(["round_no", "assister_id"]).size().rename("assists")
    hs = kills[kills["headshot"].astype(bool)].groupby(["round_no", "attacker_id"]).size().rename("hs_kills")
    dm = dmg.groupby(["round_no", "attacker_id"])["dmg_effective"].sum().rename("damage")

    pr = pr.set_index(["round_no", "steam_id"])
    for s in (k, d, a, hs, dm):
        s.index = s.index.set_names(["round_no", "steam_id"])
        pr = pr.join(s)
    pr = pr.fillna({"kills": 0, "deaths": 0, "assists": 0, "hs_kills": 0, "damage": 0}).reset_index()
    for c in ("kills", "deaths", "assists", "hs_kills", "damage"):
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
    pr["kast"] = (pr["kills"] > 0) | (pr["assists"] > 0) | pr["survived"] | pr["traded"]
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
    out["opening_attempt_pct"] = out["opening_attempts"] / out["rounds"]
    out["opening_success_pct"] = out["opening_wins"] / out["opening_attempts"].replace(0, np.nan)
    return out


# --------------------------------------------------------------------------- utility

def _utility_value(inv) -> int:
    if inv is None or (isinstance(inv, float) and np.isnan(inv)):
        return 0
    total = 0
    for item in list(inv):
        total += GRENADE_PRICES.get(str(item).lower(), 0)
    return total


def utility_metrics(p: ParsedDemo) -> pd.DataFrame:
    ids = p.players["steam_id"]
    out = pd.DataFrame(index=pd.Index(ids, name="steam_id"))

    thrown = p.grenades.groupby(["thrower_id", "type"]).size().unstack(fill_value=0)
    for t in ("flash", "smoke", "he", "molotov"):
        out[f"{t}_thrown"] = thrown[t].reindex(out.index).fillna(0).astype(int) if t in thrown else 0

    bl = p.blinds[p.blinds["thrower_id"].notna()]
    long = bl[bl["duration"] > MIN_BLIND_SECONDS]
    enemy = long[~long["is_teammate"]]
    friend = long[long["is_teammate"] | (long["thrower_id"] == long["victim_id"])]
    out["enemies_flashed"] = enemy.groupby("thrower_id").size().reindex(out.index).fillna(0).astype(int)
    out["friends_flashed"] = friend.groupby("thrower_id").size().reindex(out.index).fillna(0).astype(int)
    out["enemies_flashed_per_flash"] = out["enemies_flashed"] / out["flash_thrown"].replace(0, np.nan)
    out["friends_flashed_per_flash"] = out["friends_flashed"] / out["flash_thrown"].replace(0, np.nan)
    out["enemy_blind_seconds_total"] = enemy.groupby("thrower_id")["duration"].sum().reindex(out.index).fillna(0)

    # Blind duration: per flash, longest enemy blind; averaged over flashes that hit >=1 enemy.
    key = "entity_id" if enemy["entity_id"].notna().any() else "tick"
    per_flash = enemy.groupby(["thrower_id", key])["duration"].max()
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

    # HE / fire damage
    dmg = p.damages[p.damages["attacker_id"].notna()]
    he = dmg[dmg["weapon"].isin(HE_DAMAGE_WEAPONS)]
    fire = dmg[dmg["weapon"].isin(FIRE_DAMAGE_WEAPONS)]
    out["he_damage_enemies"] = he[~he["is_team"]].groupby("attacker_id")["dmg_effective"].sum().reindex(out.index).fillna(0)
    out["he_damage_team"] = he[he["is_team"] & (he["attacker_id"] != he["victim_id"])].groupby("attacker_id")["dmg_effective"].sum().reindex(out.index).fillna(0)
    out["he_damage_per_he"] = out["he_damage_enemies"] / out["he_thrown"].replace(0, np.nan)
    out["he_team_damage_per_he"] = out["he_damage_team"] / out["he_thrown"].replace(0, np.nan)
    out["molotov_damage_enemies"] = fire[~fire["is_team"]].groupby("attacker_id")["dmg_effective"].sum().reindex(out.index).fillna(0)

    # Unused utility on death
    inv = p.death_inventory.copy()
    if not inv.empty:
        deaths = p.kills[["tick", "victim_id"]].rename(columns={"victim_id": "steam_id"})
        inv = deaths.merge(inv, on=["tick", "steam_id"], how="left")
        inv["value"] = inv["inventory"].map(_utility_value)
        out["unused_utility_on_death_avg"] = inv.groupby("steam_id")["value"].mean().reindex(out.index)
    else:
        out["unused_utility_on_death_avg"] = np.nan
    return out


# --------------------------------------------------------------------------- all

def compute_match_metrics(p: ParsedDemo) -> pd.DataFrame:
    pr = build_player_rounds(p)
    gen = general_metrics(p, pr)
    util = utility_metrics(p)
    names = p.players.set_index("steam_id")[["name", "team"]]
    return names.join(gen).join(util)
