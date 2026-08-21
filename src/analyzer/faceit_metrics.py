import pandas as pd
import numpy as np
from typing import Dict
from demoparser2 import DemoParser
from src.analyzer.schemas import (
    FullMatchFaceitMetrics, GeneralPlayerStats, AdvancedPlayerStats,
    EntryStats, TradeStats, ClutchStats
)

def compute_faceit_metrics(demo_path: str) -> FullMatchFaceitMetrics:
    parser = DemoParser(demo_path)
    header = parser.parse_header()
    map_name = header.get("map_name", "unknown")

    # 1. Parse Key Events
    deaths_df = parser.parse_event("player_death")
    shots_df = parser.parse_event("weapon_fire", player=["velocity_X", "velocity_Y", "velocity_Z"])
    round_ends = parser.parse_event("round_end")

    total_rounds = len(round_ends) if not round_ends.empty else 1

    # Unique Players
    players = set()
    if not deaths_df.empty:
        players.update(deaths_df["user_name"].dropna().unique())
        players.update(deaths_df["attacker_name"].dropna().unique())
    players.discard(None)

    general_dict: Dict[str, GeneralPlayerStats] = {}
    advanced_dict: Dict[str, AdvancedPlayerStats] = {}
    entry_dict: Dict[str, EntryStats] = {}
    trade_dict: Dict[str, TradeStats] = {}
    clutch_dict: Dict[str, ClutchStats] = {}

    for p in players:
        general_dict[p] = GeneralPlayerStats(player_name=p, steamid="")
        advanced_dict[p] = AdvancedPlayerStats(player_name=p)
        entry_dict[p] = EntryStats(player_name=p)
        trade_dict[p] = TradeStats(player_name=p)
        clutch_dict[p] = ClutchStats(player_name=p)

    if not deaths_df.empty:
        # Kills, Deaths, Assists, HS
        for p in players:
            p_kills = deaths_df[deaths_df["attacker_name"] == p]
            p_deaths = deaths_df[deaths_df["user_name"] == p]
            p_assists = deaths_df[deaths_df["assister_name"] == p]

            k_cnt = len(p_kills)
            d_cnt = len(p_deaths)
            a_cnt = len(p_assists)
            hs_cnt = p_kills["headshot"].sum() if "headshot" in p_kills.columns else 0

            g = general_dict[p]
            g.kills = k_cnt
            g.deaths = d_cnt
            g.assists = a_cnt
            g.hs_kills = int(hs_cnt)
            g.hs_percent = (hs_cnt / k_cnt * 100.0) if k_cnt > 0 else 0.0
            g.kd_ratio = round(k_cnt / max(1, d_cnt), 2)
            g.kr_ratio = round(k_cnt / max(1, total_rounds), 2)
            g.kda = round((k_cnt + a_cnt) / max(1, d_cnt), 2)

    # Calculate Shot Accuracy & Counter-Strafe per Player
    if not shots_df.empty:
        bullet_shots = shots_df[~shots_df["weapon"].str.contains("knife|bayonet|grenade|flashbang|decoy|molotov|smoke|hegrenade|c4", case=False, na=False)].copy()
        if not bullet_shots.empty:
            vx = bullet_shots.get("user_velocity_X", 0)
            vy = bullet_shots.get("user_velocity_Y", 0)
            vz = bullet_shots.get("user_velocity_Z", 0)
            bullet_shots["speed"] = np.sqrt(vx**2 + vy**2 + vz**2)
            bullet_shots["is_accurate"] = bullet_shots["speed"] < 34.0

            for p in players:
                p_shots = bullet_shots[bullet_shots["user_name"] == p]
                if not p_shots.empty:
                    adv = advanced_dict[p]
                    adv.total_shots = len(p_shots)
                    accurate_count = p_shots["is_accurate"].sum()
                    adv.counter_strafe_accuracy_percent = round((accurate_count / len(p_shots)) * 100.0, 1)

    return FullMatchFaceitMetrics(
        map_name=map_name,
        total_rounds=total_rounds,
        general=general_dict,
        advanced=advanced_dict,
        entry=entry_dict,
        trade=trade_dict,
        clutch=clutch_dict
    )
