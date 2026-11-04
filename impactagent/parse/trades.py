"""trade_windows: one row per (death, teammate of the victim alive at the death tick).

Features are sampled from tick data inside the trade window only; no tick data is stored
(see docs/design/data-model.md, `trade_windows`). Which features make an "opportunity" or an
"attempt" is decided in impactagent/metrics (docs/metrics/leetify-metrics-spec.md §3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from demoparser2 import DemoParser

SAMPLE_EVERY_TICKS = 4  # 16 Hz is enough to catch a spot / aim within a ~4 s window

COLUMNS = [
    "round_no", "death_tick", "dead_id", "killer_id", "teammate_id",
    "dist_to_victim", "dist_to_killer", "min_dist_to_killer",
    "teammate_spotted_killer", "killer_spotted_teammate", "min_aim_angle_spotted",
    "damaged_killer", "fired", "succeeded",
]


def _ids(v) -> set[str]:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return set()
    return {str(x) for x in list(v)}


def build_trade_windows(
    parser: DemoParser,
    kills: pd.DataFrame,
    damages: pd.DataFrame,
    shots: pd.DataFrame,
    player_rounds_side: pd.DataFrame,
    tickrate: int,
    window_seconds: float,
) -> pd.DataFrame:
    w = int(window_seconds * tickrate)
    k = kills[~kills["post_match"]] if "post_match" in kills else kills
    deaths = k[~k["is_team_kill"] & ~k["is_suicide"] & k["attacker_id"].notna()]
    if deaths.empty:
        return pd.DataFrame(columns=COLUMNS)

    ticks = sorted({t for d in deaths["tick"] for t in range(int(d), int(d) + w + 1, SAMPLE_EVERY_TICKS)})
    tk = pd.DataFrame(
        parser.parse_ticks(["X", "Y", "Z", "pitch", "yaw", "is_alive", "approximate_spotted_by"], ticks=ticks)
    )
    tk["sid"] = tk["steamid"].astype("string")
    tk = tk.set_index(["tick", "sid"]).sort_index()
    mates_by = player_rounds_side.groupby(["round_no", "side"])["steam_id"].apply(list).to_dict()

    rows = []
    for d in deaths.itertuples(index=False):
        t0, v, kl = int(d.tick), d.victim_id, d.attacker_id
        if (t0, kl) not in tk.index:
            continue
        k0 = tk.loc[(t0, kl)]
        vpos = np.array([d.victim_x, d.victim_y, d.victim_z], dtype=float)
        for m in mates_by.get((d.round_no, d.victim_side), []):
            if m == v or (t0, m) not in tk.index:
                continue
            m0 = tk.loc[(t0, m)]
            if not bool(m0["is_alive"]):
                continue
            sm = sk = False
            min_d, min_ang = np.inf, np.inf
            for t in range(t0, t0 + w + 1, SAMPLE_EVERY_TICKS):
                if (t, m) not in tk.index or (t, kl) not in tk.index:
                    continue
                a, b = tk.loc[(t, m)], tk.loc[(t, kl)]
                if not (bool(a["is_alive"]) and bool(b["is_alive"])):
                    continue
                vec = np.array([b["X"] - a["X"], b["Y"] - a["Y"], b["Z"] - a["Z"]], dtype=float)
                dist = float(np.linalg.norm(vec))
                min_d = min(min_d, dist)
                sees = str(m) in _ids(b["approximate_spotted_by"])
                sm |= sees
                sk |= str(kl) in _ids(a["approximate_spotted_by"])
                if sees and dist > 0:
                    yaw, pitch = np.radians(a["yaw"]), np.radians(a["pitch"])
                    view = np.array([np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), -np.sin(pitch)])
                    min_ang = min(min_ang, float(np.degrees(np.arccos(np.clip(vec @ view / dist, -1, 1)))))
            in_w = lambda df, col: (df["tick"] > t0) & (df["tick"] <= t0 + w)  # noqa: E731
            dm = damages[(damages["attacker_id"] == m) & (damages["victim_id"] == kl)]
            sh = shots[(shots["shooter_id"] == m) & (shots["round_no"] == d.round_no)]
            kk = k[(k["attacker_id"] == m) & (k["victim_id"] == kl)]
            rows.append(
                {
                    "round_no": d.round_no,
                    "death_tick": t0,
                    "dead_id": v,
                    "killer_id": kl,
                    "teammate_id": m,
                    "dist_to_victim": float(np.linalg.norm(np.array([m0["X"], m0["Y"], m0["Z"]], dtype=float) - vpos)),
                    "dist_to_killer": float(np.linalg.norm(np.array([m0["X"] - k0["X"], m0["Y"] - k0["Y"], m0["Z"] - k0["Z"]], dtype=float))),
                    "min_dist_to_killer": min_d,
                    "teammate_spotted_killer": sm,
                    "killer_spotted_teammate": sk,
                    "min_aim_angle_spotted": min_ang,
                    "damaged_killer": bool(in_w(dm, "tick").any()),
                    "fired": bool(in_w(sh, "tick").any()),
                    "succeeded": bool(in_w(kk, "tick").any()),
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)
