"""Aim metrics per player (spec §1). Ratios keep numerator / denominator columns.

Inputs: shots with features and engagements from impactagent/parse/aim.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from impactagent.constants import (
    COUNTER_STRAFE_SPEED_FRACTION,
    RIFLES,
    SNIPERS,
    SPRAY_FIRST_COUNTED_SHOT,
    SPRAY_MIN_SHOTS,
    TTD_MAX_SECONDS,
    WEAPON_MAX_SPEED,
)


def _count(mask: pd.Series, by: pd.Series, index: pd.Index) -> pd.Series:
    return mask.groupby(by).sum().reindex(index).fillna(0).astype(int)


def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.replace(0, np.nan)


def aim_metrics(p) -> pd.DataFrame:
    out = pd.DataFrame(index=pd.Index(p.players["steam_id"], name="steam_id"))
    s = p.shots
    if "hit" not in s:  # parsed without aim tables
        return out
    s = s[s["aim_shot"]]  # guns, no shotguns, not fired in the shooter's death tick
    by = s["shooter_id"]
    one = pd.Series(True, index=s.index)

    # Gun shots in the round window (after round_end too); no knife / taser / grenades / shotguns,
    # nor shots in the tick the shooter died.
    out["shots_fired"] = _count(one, by, out.index)
    out["shots_hit"] = _count(s["hit"], by, out.index)
    out["accuracy_all"] = _ratio(out["shots_hit"], out["shots_fired"])

    sp = s["enemy_spotted"].astype(bool)
    out["shots_fired_enemy_spotted"] = _count(sp, by, out.index)
    out["shots_hit_enemy_spotted"] = _count(sp & s["hit"], by, out.index)
    out["accuracy_enemy_spotted"] = _ratio(out["shots_hit_enemy_spotted"], out["shots_fired_enemy_spotted"])

    # Head accuracy: shots that hit an enemy in the head / shots that hit an enemy, AWP excluded.
    na = s["weapon"] != "awp"
    out["head_hits"] = _count(na & s["hit_head"], by, out.index)
    out["hits_no_awp"] = _count(na & s["hit"], by, out.index)
    out["accuracy_head"] = _ratio(out["head_hits"], out["hits_no_awp"])

    # Spray: rifle sprays of >= SPRAY_MIN_SHOTS; shots from SPRAY_FIRST_COUNTED_SHOT on, enemy seen.
    spray = (s["weapon"].isin(RIFLES) & (s["spray_len"] >= SPRAY_MIN_SHOTS)
             & (s["shot_index_in_spray"] >= SPRAY_FIRST_COUNTED_SHOT) & sp)
    out["spray_shots"] = _count(spray, by, out.index)
    out["spray_hits"] = _count(spray & s["hit"], by, out.index)
    out["spray_accuracy"] = _ratio(out["spray_hits"], out["spray_shots"])

    # Counter-strafe: rifle shots at a seen enemy, not ducking; good = slower than 34% of max speed.
    cs = s["weapon"].isin(RIFLES) & sp & ~s["ducking"].fillna(False).astype(bool)
    good = cs & (s["speed_2d"] < COUNTER_STRAFE_SPEED_FRACTION * s["weapon"].map(WEAPON_MAX_SPEED))
    out["counter_strafe_shots"] = _count(cs, by, out.index)
    out["counter_strafe_good"] = _count(good, by, out.index)
    out["counter_strafe_pct"] = _ratio(out["counter_strafe_good"], out["counter_strafe_shots"])

    # First bullet: first shot after a pause, enemy seen, snipers excluded (HYPOTHESIS).
    fb = s["first_bullet"].astype(bool) & sp & ~s["weapon"].isin(SNIPERS)
    out["first_bullets"] = _count(fb, by, out.index)
    out["first_bullet_hits"] = _count(fb & s["hit"], by, out.index)
    out["first_bullet_accuracy"] = _ratio(out["first_bullet_hits"], out["first_bullets"])

    # Engagement medians (time to damage, crosshair placement: < 1 s; time to kill: all).
    e = p.engagements
    if e is not None and not e.empty:
        quick = e[e["ttd_ms"].notna() & (e["ttd_ms"] < TTD_MAX_SECONDS * 1000)]
        out["ttd_ms"] = quick.groupby("attacker_id")["ttd_ms"].median().astype(float).reindex(out.index)
        out["crosshair_placement_deg"] = quick.groupby("attacker_id")["crosshair_err_deg"].median().astype(float).reindex(out.index)
        kills = e[e["ttk_ms"].notna()]
        out["ttk_ms"] = kills.groupby("attacker_id")["ttk_ms"].median().astype(float).reindex(out.index)
    else:
        out["ttd_ms"] = out["crosshair_placement_deg"] = out["ttk_ms"] = np.nan
    return out
