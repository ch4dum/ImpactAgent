import json
import os
from typing import Dict, Any, Optional
from src.analyzer.schemas import FullMatchFaceitMetrics

SYSTEM_COACH_PROMPT = """You are ImpactAgent, an elite Counter-Strike 2 (CS2) AI Tactical Coach.
Your goal is to provide deep, evidence-based, actionable coaching for a specific player and their team's macro performance based on exact replay match telemetry.

Structure your coaching report into two distinct, highly detailed sections:

---
### 👤 SECTION 1: INDIVIDUAL PLAYER DIAGNOSIS ({target_player})

1. **Mechanics & Physical Readiness:**
   - Analyze Shot Accuracy, Counter-Strafe Quality (% of shots fired under 34 u/s speed), and Reaction Time/Time-to-Damage.
   - Note if the player seems fatigued or mechanically off today.

2. **Repeated Tactical Mistakes & Over-Extensions:**
   - Identify bad habits (e.g. over-pushing Top Mid/A-ramps, solo peeking without support, peeking into established crossfires).
   - Point out specific rounds where over-pushing resulted in early deaths or lost rounds.

3. **Utility & Engagement Habits:**
   - Flashes self-blinding vs enemy blinding duration, wasted utility.

4. **3 Actionable Personal Drills/Fixes for Next Game:**
   - Provide concrete advice (e.g., "On T-side Mirage, hold Mid control with flash support instead of solo peeking Top Mid").

---
### 🗺️ SECTION 2: TEAM MACRO & MAP CONTROL ANALYSIS

1. **Information Leakage & Enemy Aggression:**
   - Identify where the enemy team frequently pushed for early info (e.g., B Apps pushes, A Main aggressive peeks) and how it compromised T-side site executes.

2. **Rotation & Site Stack Reads:**
   - Analyze how fast the enemy rotated to stack defense sites due to poor map control or slow executes.

3. **Team Positioning & Trade Alignment:**
   - Analyze trade window latencies and support spacing during site hits.

Maintain a professional, constructive, and highly analytical coaching tone. Reference exact numbers from the data payload.
"""

def generate_coach_prompt(match_data: FullMatchFaceitMetrics, target_player: str) -> str:
    """Formats the match telemetry into a high-signal JSON payload for the LLM Coach"""
    
    # Extract Target Player Stats
    p_gen = match_data.general.get(target_player)
    p_adv = match_data.advanced.get(target_player)
    p_ent = match_data.entry.get(target_player)
    p_trd = match_data.trade.get(target_player)
    p_clu = match_data.clutch.get(target_player)

    player_summary = {
        "player_name": target_player,
        "general": p_gen.model_dump() if p_gen else {},
        "advanced": p_adv.model_dump() if p_adv else {},
        "entry": p_ent.model_dump() if p_ent else {},
        "trade": p_trd.model_dump() if p_trd else {},
        "clutch": p_clu.model_dump() if p_clu else {}
    }

    # Match Overview
    match_summary = {
        "map_name": match_data.map_name,
        "total_rounds": match_data.total_rounds,
        "all_players_kd": {p: match_data.general[p].kd_ratio for p in match_data.general}
    }

    prompt = f"""[MATCH TELEMETRY PAYLOAD]
Map: {match_summary['map_name']} | Total Rounds: {match_summary['total_rounds']}

[TARGET PLAYER DATA: {target_player}]
{json.dumps(player_summary, indent=2)}

[MATCH CONTEXT: ALL PLAYERS K/D]
{json.dumps(match_summary['all_players_kd'], indent=2)}

Please generate the complete Coaching Report for {target_player} following the system guidelines.
"""
    return prompt

class ImpactAgentCoach:
    def __init__(self, provider: str = "mock", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.getenv("LLM_API_KEY")

    def generate_report(self, match_data: FullMatchFaceitMetrics, target_player: str) -> str:
        prompt_text = generate_coach_prompt(match_data, target_player)

        if self.provider == "mock" or not self.api_key:
            # Generate a structured preview mock report if API key is not provided yet
            return f"""# 🏆 ImpactAgent AI Coaching Report for [{target_player}]
**Map:** {match_data.map_name} | **Rounds:** {match_data.total_rounds}

---
### 👤 SECTION 1: INDIVIDUAL PLAYER DIAGNOSIS ({target_player})

#### 1. Mechanics & Physical Readiness
- **Counter-Strafe Accuracy:** {match_data.advanced.get(target_player, {}).counter_strafe_accuracy_percent if target_player in match_data.advanced else 'N/A'}%
- **Analysis:** Your counter-strafe consistency is moderate. You had multiple engagements where velocity was >34 u/s during firing, indicating slight movement inaccuracy under pressure.

#### 2. Repeated Tactical Mistakes & Over-Extensions
- **Top Mid / Aggressive Peeks:** High frequency of solo peeking without support flash on Mirage Mid.
- **Crosshair Placement:** Time-to-damage was elevated on A-Site retakes due to crosshair resting at chest height instead of head angle.

#### 3. Actionable Fixes:
1. Stop solo peeking Top Mid without a teammate holding flash support.
2. Practice counter-strafe timing on community DM servers before matches.
3. Pre-aim Bench and Palace angles at head level before peeking.

---
### 🗺️ SECTION 2: TEAM MACRO & MAP CONTROL ANALYSIS

#### 1. Enemy Info Pushes & Map Control
- The enemy team consistently pushed B Apartments and Connector early in the round to gain information.
- Because your team did not contest Mid control early, the enemy rotated 3-4 players to the target site before your execute arrived.

---
*(Note: Connect an API Key for OpenAI / Gemini / Claude / Ollama to generate real-time AI responses)*
"""
        # Additional API integrations (OpenAI / Gemini / Anthropic) will connect here
        return "LLM integration ready."
