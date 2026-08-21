from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class MatchHeader(BaseModel):
    match_id: str
    map_name: str
    finished_at: Optional[str] = None
    data_source: Optional[str] = None
    team_scores: List[int] = [0, 0]
    ticks: Optional[int] = None
    tickrate: Optional[int] = None

class PlayerRatings(BaseModel):
    steam64_id: str
    player_name: str
    leetify_rating: float = 0.0
    ct_leetify_rating: float = 0.0
    t_leetify_rating: float = 0.0
    hltv_rating: float = 0.0
    score: int = 0
    mvps: int = 0

class PlayerAimStats(BaseModel):
    preaim_deg: float = Field(0.0, description="Crosshair placement error in degrees")
    reaction_time_sec: float = Field(0.0, description="Time to damage in seconds")
    accuracy_all: float = Field(0.0, description="All shots accuracy ratio")
    accuracy_enemy_spotted: float = Field(0.0, description="Enemy spotted accuracy ratio")
    accuracy_head: float = Field(0.0, description="Headshot accuracy ratio")
    hsp_percent: float = Field(0.0, description="Headshot kill percentage")
    spray_accuracy: float = Field(0.0, description="Spray accuracy (shots 2-10)")
    counter_strafing_good_ratio: float = Field(0.0, description="Accurate counter-strafe ratio (<34 u/s)")
    counter_strafing_good_shots: int = 0
    counter_strafing_bad_shots: int = 0
    shots_fired: int = 0
    shots_fired_enemy_spotted: int = 0
    shots_hit_foe: int = 0

class PlayerGeneralStats(BaseModel):
    total_kills: int = 0
    total_deaths: int = 0
    total_assists: int = 0
    total_hs_kills: int = 0
    kd_ratio: float = 0.0
    total_damage: int = 0
    dpr: float = Field(0.0, description="ADR / Damage per round")
    kast: float = Field(0.0, description="KAST ratio")
    rounds_survived: int = 0
    multi_1k: int = 0
    multi_2k: int = 0
    multi_3k: int = 0
    multi_4k: int = 0
    multi_5k: int = 0
    total_reloads: int = 0
    total_wasted_magazine_ammo: int = 0
    wasted_magazine_ammo_pct: float = Field(0.0, description="% magazine ammo wasted on early reload")

class PlayerTradeStats(BaseModel):
    trade_kill_opportunities: int = 0
    trade_kill_attempts: int = 0
    trade_kills_succeed: int = 0
    trade_kill_success_pct: float = 0.0
    traded_death_opportunities: int = 0
    traded_death_attempts: int = 0
    traded_deaths_succeed: int = 0
    traded_deaths_success_pct: float = 0.0

class PlayerUtilityStats(BaseModel):
    utility_on_death_avg_cost: float = Field(0.0, description="Avg $ value of utility held on death")
    he_thrown: int = 0
    he_foes_damage_avg: float = 0.0
    he_friends_damage_avg: float = 0.0
    molotov_thrown: int = 0
    smoke_thrown: int = 0
    flashbang_thrown: int = 0
    flashbang_hit_foe: int = 0
    flashbang_hit_friend: int = 0
    flashbang_hit_foe_avg_duration_sec: float = 0.0
    flashbang_leading_to_kill: int = 0
    flash_assist: int = 0

class OpeningDuelEvent(BaseModel):
    round_num: int
    tick: int
    round_time_sec: int
    attacker_name: str
    victim_name: str
    weapon_name: str
    traded: bool

class ClutchEvent(BaseModel):
    round_num: int
    player_steam64_id: str
    handicap: int = Field(..., description="-1 = 1v1, -2 = 1v2, -3 = 1v3, etc.")
    attempts: int
    clutches_won: int
    total_kills: int

class FullMatchTelemetry(BaseModel):
    header: MatchHeader
    ratings: Dict[str, PlayerRatings] = {}
    aim: Dict[str, PlayerAimStats] = {}
    general: Dict[str, PlayerGeneralStats] = {}
    trade: Dict[str, PlayerTradeStats] = {}
    utility: Dict[str, PlayerUtilityStats] = {}
    opening_duels: List[OpeningDuelEvent] = []
    clutches: List[ClutchEvent] = []
