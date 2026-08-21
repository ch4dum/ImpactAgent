import json
import os
from typing import Dict, Any, Optional, List
from src.analyzer.schemas import FullMatchTelemetry

class AgenticCS2Coach:
    """Agentic Tool-Calling LLM Coach for ImpactAgent"""

    def __init__(self, match_telemetry: FullMatchTelemetry, target_player: str = "ch4dum"):
        self.telemetry = match_telemetry
        self.target_player = target_player

    # Tool 1: Query Player Stats Summary
    def tool_get_player_summary(self, player_name: str) -> Dict[str, Any]:
        """Returns complete 5-category stats summary for a specific player"""
        if player_name not in self.telemetry.general:
            return {"error": f"Player '{player_name}' not found in match."}

        return {
            "player_name": player_name,
            "ratings": self.telemetry.ratings[player_name].model_dump() if player_name in self.telemetry.ratings else {},
            "aim": self.telemetry.aim[player_name].model_dump() if player_name in self.telemetry.aim else {},
            "general": self.telemetry.general[player_name].model_dump() if player_name in self.telemetry.general else {},
            "trade": self.telemetry.trade[player_name].model_dump() if player_name in self.telemetry.trade else {},
            "utility": self.telemetry.utility[player_name].model_dump() if player_name in self.telemetry.utility else {}
        }

    # Tool 2: Query Opening Duels
    def tool_get_opening_duels(self, filter_player: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns opening duels log, optionally filtered by a specific player"""
        duels = []
        for od in self.telemetry.opening_duels:
            if not filter_player or filter_player in (od.attacker_name, od.victim_name):
                duels.append(od.model_dump())
        return duels

    # Tool 3: Query Clutches
    def tool_get_clutches(self, filter_steam_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns clutch events log"""
        clutches = []
        for cl in self.telemetry.clutches:
            if not filter_steam_id or filter_steam_id == cl.player_steam64_id:
                clutches.append(cl.model_dump())
        return clutches

    # Tool 4: Generate Full Diagnostic Executive Summary
    def generate_executive_coaching_report(self, target_player: Optional[str] = None) -> str:
        p_name = target_player or self.target_player
        p_stats = self.tool_get_player_summary(p_name)
        
        if "error" in p_stats:
            return f"Error: {p_stats['error']}"

        ratings = p_stats["ratings"]
        aim = p_stats["aim"]
        general = p_stats["general"]
        trade = p_stats["trade"]
        utility = p_stats["utility"]

        # Filter Opening Duels for target player
        player_opening_duels = self.tool_get_opening_duels(filter_player=p_name)

        report = f"""# 🏆 ImpactAgent AI Tactical Coaching Report
**Map:** {self.telemetry.header.map_name.upper()} | **Score:** {self.telemetry.header.team_scores[0]} - {self.telemetry.header.team_scores[1]} | **Target Player:** [{p_name}]

---
## 1. 🎯 Aim & Mechanical Readiness Analysis
- **Crosshair Placement Error:** `{aim.get('preaim_deg', 0)}°`
- **Reaction Time (Time to Damage):** `{aim.get('reaction_time_sec', 0)*1000:.0f} ms`
- **Counter-Strafe Accuracy:** `{aim.get('counter_strafing_good_ratio', 0)}%` ({aim.get('counter_strafing_good_shots', 0)} shots accurate / {aim.get('counter_strafing_bad_shots', 0)} shots moving)
- **Enemy Spotted Accuracy:** `{aim.get('accuracy_enemy_spotted', 0)}%` | **Headshot Kill %:** `{aim.get('hsp_percent', 0)}%`
- **Diagnosis:**
  - {"✅ Excellent crosshair placement." if aim.get('preaim_deg', 99) < 6.0 else "⚠️ Crosshair placement needs improvement. Aim is resting away from head level when peeking."}
  - {"✅ Strong counter-strafe consistency." if aim.get('counter_strafing_good_ratio', 0) > 75 else "⚠️ High proportion of moving shots. Practice counter-strafe timing."}

---
## 2. 🤺 Opening Duels & Tactical Extensions
- **Total Opening Duels Involved:** {len(player_opening_duels)}
"""
        if player_opening_duels:
            report += "  **Opening Duels Log:**\n"
            for od in player_opening_duels[:5]:
                role = "WINNER" if od['attacker_name'] == p_name else "VICTIM"
                status = "Traded" if od['traded'] else "NOT TRADED (Died Alone)"
                report += f"  - Round {od['round_num']} ({od['round_time_sec']}s in): {role} vs {od['victim_name'] if role == 'WINNER' else od['attacker_name']} ({od['weapon_name']}) -> {status}\n"

        report += f"""
---
## 3. 💣 Utility & Economic Efficiency
- **Avg Utility Value Held on Death:** `${utility.get('utility_on_death_avg_cost', 0):.2f}`
- **Flashes Thrown:** `{utility.get('flashbang_thrown', 0)}` (Blinded Enemies: `{utility.get('flashbang_hit_foe', 0)}`, Blinded Friends: `{utility.get('flashbang_hit_friend', 0)}`)
- **Avg Enemy Blind Duration:** `{utility.get('flashbang_hit_foe_avg_duration_sec', 0)}s`
- **Flash Kills Generated:** `{utility.get('flashbang_leading_to_kill', 0)}`

---
## 4. 🔄 Trade Efficiency & Team Spacing
- **Trade Kill Success Rate:** `{trade.get('trade_kill_success_pct', 0)}%` ({trade.get('trade_kills_succeed', 0)}/ {trade.get('trade_kill_opportunities', 0)} opportunities)
- **Traded Deaths Success Rate:** `{trade.get('traded_deaths_success_pct', 0)}%` ({trade.get('traded_deaths_succeed', 0)}/ {trade.get('traded_death_opportunities', 0)} times teammate traded you)

---
## 💡 Top 3 Actionable Homework Fixes:
1. **Fix Entry Spacing:** In opening duels where you died untraded, ensure a support teammate is holding a flash or trading angle within 1.5 seconds.
2. **Utility Retention:** Do not carry over `${utility.get('utility_on_death_avg_cost', 0):.0f}` of unused utility into combat. Use utility early for territory control.
3. **Counter-Strafe Discipline:** Maintain shot accuracy by bringing velocity below 34 u/s before pulling trigger.
"""
        return report
