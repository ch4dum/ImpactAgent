import requests
import json
import os
from typing import Dict, Any, Optional, List
from src.analyzer.schemas import (
    FullMatchTelemetry, MatchHeader, PlayerRatings, PlayerAimStats,
    PlayerGeneralStats, PlayerTradeStats, PlayerUtilityStats,
    OpeningDuelEvent, ClutchEvent
)

class LeetifyScraperEngine:
    """Live API Scraper & Extractor targeting Leetify V2 Public endpoints"""

    PUBLIC_API_URL = "https://api-public.cs-prod.leetify.com/v2/matches"
    MAIN_API_URL = "https://api.leetify.com/api/games"

    def __init__(self, match_id_or_url: str):
        self.match_id = self._extract_match_id(match_id_or_url)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })

    def _extract_match_id(self, match_id_or_url: str) -> str:
        clean = match_id_or_url.strip()
        if "leetify.com" in clean:
            parts = clean.split("/")
            for p in parts:
                if len(p) >= 32 and "-" in p:
                    return p
        return clean

    def fetch_full_telemetry(self) -> FullMatchTelemetry:
        """Fetches and merges all sub-endpoints into FullMatchTelemetry"""
        
        v2_url = f"{self.PUBLIC_API_URL}/{self.match_id}"
        resp_v2 = self.session.get(v2_url, timeout=10)
        
        if resp_v2.status_code != 200:
            raise RuntimeError(f"Failed to fetch match data from Leetify API (Status Code: {resp_v2.status_code})")

        v2_json = resp_v2.json()

        # Parse team scores safely
        raw_scores = v2_json.get("team_scores", [])
        parsed_scores = []
        if isinstance(raw_scores, list):
            for item in raw_scores:
                if isinstance(item, dict):
                    parsed_scores.append(item.get("score", 0))
                elif isinstance(item, int):
                    parsed_scores.append(item)

        header = MatchHeader(
            match_id=v2_json.get("id", self.match_id),
            map_name=v2_json.get("map_name", "unknown"),
            finished_at=v2_json.get("finished_at"),
            data_source=v2_json.get("data_source"),
            team_scores=parsed_scores if parsed_scores else [0, 0]
        )

        ratings_map = {}
        aim_map = {}
        general_map = {}
        trade_map = {}
        utility_map = {}

        for p in v2_json.get("stats", []):
            name = p.get("name", "Unknown")
            steam_id = p.get("steam64_id", "")

            ratings_map[name] = PlayerRatings(
                steam64_id=steam_id,
                player_name=name,
                leetify_rating=round(p.get("leetify_rating", 0.0) * 100, 2),
                ct_leetify_rating=round(p.get("ct_leetify_rating", 0.0) * 100, 2),
                t_leetify_rating=round(p.get("t_leetify_rating", 0.0) * 100, 2),
                hltv_rating=p.get("hltv_rating", 0.0),
                score=p.get("score", 0),
                mvps=p.get("mvps", 0)
            )

            aim_map[name] = PlayerAimStats(
                preaim_deg=round(p.get("preaim", 0.0), 2),
                reaction_time_sec=round(p.get("reaction_time", 0.0), 3),
                accuracy_all=round(p.get("accuracy", 0.0) * 100, 1),
                accuracy_enemy_spotted=round(p.get("accuracy_enemy_spotted", 0.0) * 100, 1),
                accuracy_head=round(p.get("accuracy_head", 0.0) * 100, 1),
                hsp_percent=round(p.get("hsp", 0.0) * 100, 1),
                spray_accuracy=round(p.get("spray_accuracy", 0.0) * 100, 1),
                counter_strafing_good_ratio=round(p.get("counter_strafing_shots_good_ratio", 0.0) * 100, 1),
                counter_strafing_good_shots=p.get("counter_strafing_shots_good", 0),
                counter_strafing_bad_shots=p.get("counter_strafing_shots_bad", 0),
                shots_fired=p.get("shots_fired", 0),
                shots_fired_enemy_spotted=p.get("shots_fired_enemy_spotted", 0),
                shots_hit_foe=p.get("shots_hit_foe", 0)
            )

            general_map[name] = PlayerGeneralStats(
                total_kills=p.get("total_kills", 0),
                total_deaths=p.get("total_deaths", 0),
                total_assists=p.get("total_assists", 0),
                total_hs_kills=p.get("total_hs_kills", 0),
                kd_ratio=p.get("kd_ratio", 0.0),
                total_damage=p.get("total_damage", 0),
                dpr=p.get("dpr", 0.0),
                kast=round(p.get("kast", 0.0) * 100, 1),
                rounds_survived=p.get("rounds_survived", 0),
                multi_1k=p.get("multi1k", 0),
                multi_2k=p.get("multi2k", 0),
                multi_3k=p.get("multi3k", 0),
                multi_4k=p.get("multi4k", 0),
                multi_5k=p.get("multi5k", 0),
                total_reloads=p.get("total_reloads", 0),
                total_wasted_magazine_ammo=p.get("total_wasted_magazine_ammo", 0),
                wasted_magazine_ammo_pct=round(p.get("wasted_magazine_ammo_pct", 0.0) * 100, 1)
            )

            trade_map[name] = PlayerTradeStats(
                trade_kill_opportunities=p.get("trade_kill_opportunities", 0),
                trade_kill_attempts=p.get("trade_kill_attempts", 0),
                trade_kills_succeed=p.get("trade_kills_succeed", 0),
                trade_kill_success_pct=round(p.get("trade_kills_success_percentage", 0.0) * 100, 1),
                traded_death_opportunities=p.get("traded_death_opportunities", 0),
                traded_death_attempts=p.get("traded_death_attempts", 0),
                traded_deaths_succeed=p.get("traded_deaths_succeed", 0),
                traded_deaths_success_pct=round(p.get("traded_deaths_success_percentage", 0.0) * 100, 1)
            )

            utility_map[name] = PlayerUtilityStats(
                utility_on_death_avg_cost=round(p.get("utility_on_death_avg", 0.0), 2),
                he_thrown=p.get("he_thrown", 0),
                he_foes_damage_avg=round(p.get("he_foes_damage_avg", 0.0), 1),
                he_friends_damage_avg=round(p.get("he_friends_damage_avg", 0.0), 1),
                molotov_thrown=p.get("molotov_thrown", 0),
                smoke_thrown=p.get("smoke_thrown", 0),
                flashbang_thrown=p.get("flashbang_thrown", 0),
                flashbang_hit_foe=p.get("flashbang_hit_foe", 0),
                flashbang_hit_friend=p.get("flashbang_hit_friend", 0),
                flashbang_hit_foe_avg_duration_sec=round(p.get("flashbang_hit_foe_avg_duration", 0.0), 2),
                flashbang_leading_to_kill=p.get("flashbang_leading_to_kill", 0),
                flash_assist=p.get("flash_assist", 0)
            )

        # Fetch Opening Duels
        opening_duels_list = []
        try:
            resp_od = self.session.get(f"{self.MAIN_API_URL}/{self.match_id}/opening-duels", timeout=5)
            if resp_od.status_code == 200:
                for od in resp_od.json():
                    weapon = od.get("attackerWeapon", {})
                    w_name = weapon.get("itemName", "Unknown") if isinstance(weapon, dict) else "Unknown"
                    opening_duels_list.append(OpeningDuelEvent(
                        round_num=od.get("round", 0),
                        tick=od.get("tick", 0),
                        round_time_sec=od.get("roundTime", 0),
                        attacker_name=od.get("attackerName", "Unknown"),
                        victim_name=od.get("victimName", "Unknown"),
                        weapon_name=w_name,
                        traded=od.get("traded", False)
                    ))
        except Exception:
            pass

        # Fetch Clutches
        clutches_list = []
        try:
            resp_cl = self.session.get(f"{self.MAIN_API_URL}/{self.match_id}/clutches", timeout=5)
            if resp_cl.status_code == 200:
                for cl in resp_cl.json():
                    clutches_list.append(ClutchEvent(
                        round_num=cl.get("roundNumber", 0),
                        player_steam64_id=cl.get("steam64Id", ""),
                        handicap=cl.get("handicap", -1),
                        attempts=cl.get("attempts", 0),
                        clutches_won=cl.get("clutchesWon", 0),
                        total_kills=cl.get("totalKills", 0)
                    ))
        except Exception:
            pass

        return FullMatchTelemetry(
            header=header,
            ratings=ratings_map,
            aim=aim_map,
            general=general_map,
            trade=trade_map,
            utility=utility_map,
            opening_duels=opening_duels_list,
            clutches=clutches_list
        )
