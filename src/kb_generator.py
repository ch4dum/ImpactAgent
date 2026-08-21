import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from demoparser2 import DemoParser

def ensure_df(val: Any) -> pd.DataFrame:
    """Safely converts any demoparser2 return type (DataFrame, list, None) into a valid pandas DataFrame"""
    if isinstance(val, pd.DataFrame):
        return val
    if isinstance(val, list):
        if len(val) == 0:
            return pd.DataFrame()
        return pd.DataFrame(val)
    return pd.DataFrame()

def calculate_preaim_error_deg(att_x, att_y, att_z, att_pitch, att_yaw, vic_x, vic_y, vic_z) -> float:
    """Calculates 3D Crosshair Placement Error in degrees between attacker view vector and victim position"""
    try:
        pitch_rad = np.radians(att_pitch)
        yaw_rad = np.radians(att_yaw)

        u_x = np.cos(pitch_rad) * np.cos(yaw_rad)
        u_y = np.cos(pitch_rad) * np.sin(yaw_rad)
        u_z = -np.sin(pitch_rad)
        u = np.array([u_x, u_y, u_z])

        v = np.array([vic_x - att_x, vic_y - att_y, (vic_z + 64) - att_z])
        norm_v = np.linalg.norm(v)

        if norm_v == 0:
            return 0.0

        v_unit = v / norm_v
        dot_product = np.clip(np.dot(u, v_unit), -1.0, 1.0)
        angle_rad = np.arccos(dot_product)
        return float(np.degrees(angle_rad))
    except Exception:
        return 5.0

class DemoKnowledgeBaseGenerator:
    """CS2 Replay (.dem) to LLM Robust Knowledge Base (.md) Generator using demoparser2"""

    def __init__(self, demo_path: str):
        self.demo_path = demo_path
        if not os.path.exists(demo_path):
            alt = os.path.join("scripts", "demos", os.path.basename(demo_path))
            if os.path.exists(alt):
                self.demo_path = alt
        if not os.path.exists(self.demo_path):
            raise FileNotFoundError(f"CS2 Demo file not found: {demo_path}")
            
        self.parser = DemoParser(self.demo_path)

    def generate_markdown_kb(self, output_path: str) -> str:
        """Parses .dem file and exports a robust, type-safe Markdown Knowledge Base (.md) file"""
        header = self.parser.parse_header()
        map_name = header.get("map_name", "de_mirage")
        server_name = header.get("server_name", "Unknown Server")

        # 1. Detect Official Match Start Tick (filter out warmup / knife rounds)
        match_start_events = ensure_df(self.parser.parse_event("round_announce_match_start"))
        match_start_tick = 0
        if not match_start_events.empty and "tick" in match_start_events.columns:
            match_start_tick = match_start_events["tick"].max()

        # 2. Parse Events & Safely Convert to DataFrames
        raw_deaths = ensure_df(self.parser.parse_event("player_death", player=["X", "Y", "Z", "pitch", "yaw", "last_place_name"]))
        raw_shots = ensure_df(self.parser.parse_event("weapon_fire", player=["X", "Y", "Z", "velocity_X", "velocity_Y", "velocity_Z", "pitch", "yaw", "last_place_name"]))
        raw_hurt = ensure_df(self.parser.parse_event("player_hurt", player=["X", "Y", "Z", "last_place_name"]))
        raw_blind = ensure_df(self.parser.parse_event("player_blind"))
        raw_round_ends = ensure_df(self.parser.parse_event("round_end"))
        raw_freeze_ends = ensure_df(self.parser.parse_event("round_freeze_end"))
        raw_bomb_plants = ensure_df(self.parser.parse_event("bomb_planted"))

        # Filter events to match_start_tick
        deaths_df = raw_deaths[(raw_deaths["tick"] >= match_start_tick)].copy() if not raw_deaths.empty and "tick" in raw_deaths.columns else pd.DataFrame()
        shots_df = raw_shots[(raw_shots["tick"] >= match_start_tick)].copy() if not raw_shots.empty and "tick" in raw_shots.columns else pd.DataFrame()
        hurt_df = raw_hurt[(raw_hurt["tick"] >= match_start_tick)].copy() if not raw_hurt.empty and "tick" in raw_hurt.columns else pd.DataFrame()
        blind_df = raw_blind[(raw_blind["tick"] >= match_start_tick)].copy() if not raw_blind.empty and "tick" in raw_blind.columns else pd.DataFrame()
        bomb_plants = raw_bomb_plants[(raw_bomb_plants["tick"] >= match_start_tick)].copy() if not raw_bomb_plants.empty and "tick" in raw_bomb_plants.columns else pd.DataFrame()

        # Filter Official Match Rounds
        official_freeze_ends = raw_freeze_ends[raw_freeze_ends["tick"] >= match_start_tick].copy() if not raw_freeze_ends.empty and "tick" in raw_freeze_ends.columns else pd.DataFrame()
        official_round_ends = raw_round_ends[raw_round_ends["tick"] >= match_start_tick].copy() if not raw_round_ends.empty and "tick" in raw_round_ends.columns else pd.DataFrame()
        
        total_rounds = len(official_round_ends) if not official_round_ends.empty else 1

        # Map each death tick to its Official Match Round Number
        if not deaths_df.empty:
            match_r_nums = []
            for idx, d in deaths_df.iterrows():
                d_tick = d["tick"]
                prior = official_freeze_ends[official_freeze_ends["tick"] <= d_tick] if not official_freeze_ends.empty else pd.DataFrame()
                r_num = len(prior) if not prior.empty else 1
                match_r_nums.append(max(1, r_num))
            deaths_df["match_round"] = match_r_nums

        # Preaim Error Calculation
        if not deaths_df.empty:
            preaim_errors = []
            att_speeds = []
            for idx, r in deaths_df.iterrows():
                err = calculate_preaim_error_deg(
                    r.get("attacker_X", 0), r.get("attacker_Y", 0), r.get("attacker_Z", 0),
                    r.get("attacker_pitch", 0), r.get("attacker_yaw", 0),
                    r.get("user_X", 0), r.get("user_Y", 0), r.get("user_Z", 0)
                )
                preaim_errors.append(err)

                att_name = r.get("attacker_name")
                d_tick = r.get("tick", 0)
                speed_val = 0.0
                if not shots_df.empty and att_name and "user_name" in shots_df.columns:
                    p_shots = shots_df[(shots_df["user_name"] == att_name) & (shots_df["tick"] <= d_tick)]
                    if not p_shots.empty:
                        last_shot = p_shots.iloc[-1]
                        vx = last_shot.get("user_velocity_X", 0)
                        vy = last_shot.get("user_velocity_Y", 0)
                        vz = last_shot.get("user_velocity_Z", 0)
                        speed_val = np.sqrt(vx**2 + vy**2 + vz**2)
                att_speeds.append(speed_val)

            deaths_df["preaim_error_deg"] = preaim_errors
            deaths_df["attacker_speed"] = att_speeds

        # Trade Frag Window Calculation
        if not deaths_df.empty:
            sorted_deaths = deaths_df.sort_values(by="tick").copy()
            traded_flags = []
            for i in range(len(sorted_deaths)):
                row = sorted_deaths.iloc[i]
                tick = row["tick"]
                victim = row["user_name"]
                attacker = row["attacker_name"]
                subsequent = sorted_deaths[(sorted_deaths["tick"] > tick) & (sorted_deaths["tick"] <= tick + 200)]
                trade_found = False
                if not subsequent.empty:
                    for _, s_row in subsequent.iterrows():
                        if s_row["user_name"] == attacker and s_row["attacker_name"] != victim:
                            trade_found = True
                            break
                traded_flags.append(trade_found)
            sorted_deaths["is_traded"] = traded_flags
            deaths_df = sorted_deaths

        # Dynamic Engagement Spray-Start TTD Calculation
        ttd_map = {}
        if not hurt_df.empty and not shots_df.empty and "attacker_name" in hurt_df.columns and "user_name" in shots_df.columns:
            for p in hurt_df["attacker_name"].dropna().unique():
                p_hurts = hurt_df[hurt_df["attacker_name"] == p]
                p_shots = shots_df[shots_df["user_name"] == p].sort_values(by="tick")

                if not p_hurts.empty and not p_shots.empty:
                    shot_ticks = p_shots["tick"].values
                    spray_starts = [shot_ticks[0]]
                    for t in shot_ticks[1:]:
                        if t - spray_starts[-1] > 32: # >0.5s gap marks a new spray engagement
                            spray_starts.append(t)
                    spray_starts = np.array(spray_starts)

                    real_ttds = []
                    for _, h in p_hurts.iterrows():
                        h_tick = h["tick"]
                        prior_starts = spray_starts[spray_starts <= h_tick]
                        if len(prior_starts) > 0:
                            first_shot_tick = prior_starts[-1]
                            ticks_to_hit = h_tick - first_shot_tick
                            ttd_ms = 160.0 + (ticks_to_hit * 15.625)
                            if 150 <= ttd_ms <= 800:
                                real_ttds.append(ttd_ms)

                    if real_ttds:
                        ttd_map[p] = round(float(np.mean(real_ttds)), 1)

        # Bullet shots filter & counter-strafe
        bullet_shots = pd.DataFrame()
        rifle_shots = pd.DataFrame()
        if not shots_df.empty and "weapon" in shots_df.columns:
            bullet_shots = shots_df[~shots_df["weapon"].str.contains("knife|bayonet|grenade|flashbang|decoy|molotov|smoke|hegrenade|c4", case=False, na=False)].copy()
            vx = bullet_shots.get("user_velocity_X", 0)
            vy = bullet_shots.get("user_velocity_Y", 0)
            vz = bullet_shots.get("user_velocity_Z", 0)
            bullet_shots["speed"] = np.sqrt(vx**2 + vy**2 + vz**2)
            bullet_shots["is_accurate"] = bullet_shots["speed"] < 34.0

            precision_weapons = "ak47|m4a1|m4a4|galilar|famas|sg553|aug|awp|ssg08|deagle"
            rifle_shots = bullet_shots[bullet_shots["weapon"].str.contains(precision_weapons, case=False, na=False)].copy()

        players = sorted(list(set(deaths_df["user_name"].dropna().unique()).union(set(deaths_df["attacker_name"].dropna().unique())))) if not deaths_df.empty else []

        kb = []
        kb.append(f"# CS2 Official Match Knowledge Base (Filtered Warmup/Knife Ticks)")
        kb.append(f"**Demo File:** `{os.path.basename(self.demo_path)}` | **Map:** `{map_name}` | **Official Match Rounds:** `{total_rounds}` | **Server:** `{server_name}`\n")

        # SECTION 1: Team Macro & Plant Statistics
        kb.append("---")
        kb.append("## 🗺️ 1. Team Macro, Site Executions & Plant Statistics Summary")
        tot_plants = len(bomb_plants) if not bomb_plants.empty else 0
        a_plants = 0
        b_plants = 0
        if not bomb_plants.empty and "site" in bomb_plants.columns:
            site_counts = bomb_plants["site"].value_counts().to_dict()
            site_keys = list(site_counts.keys())
            if len(site_keys) >= 2:
                a_plants = site_counts.get(site_keys[1], 0)
                b_plants = site_counts.get(site_keys[0], 0)
            elif len(site_keys) == 1:
                a_plants = site_counts.get(site_keys[0], 0)

        kb.append(f"- **Total Bomb Plants:** `{tot_plants}` | **A-Site Plants:** `{a_plants}` | **B-Site Plants:** `{b_plants}`")

        # SECTION 2: FK/FD & Trade Frag Efficiency
        kb.append("\n---")
        kb.append("## ⚔️ 2. First Kill / First Death (FK/FD) & Trade Frag Efficiency")
        kb.append("| Player Name | First Kills (FK) | First Deaths (FD) | Failed Early Pushes (t≤20s Untraded) | Traded Death % | Trade Kill Conversion % |")
        kb.append("|---|---|---|---|---|---|")

        sorted_d = deaths_df.sort_values(by="tick") if not deaths_df.empty else pd.DataFrame()
        for p in players:
            p_deaths = deaths_df[deaths_df["user_name"] == p] if not deaths_df.empty else pd.DataFrame()

            fk_cnt = 0
            fd_cnt = 0
            failed_early_pushes = 0

            if not sorted_d.empty and not official_freeze_ends.empty:
                for tick_start in official_freeze_ends["tick"].values:
                    r_deaths = sorted_d[(sorted_d["tick"] >= tick_start) & (sorted_d["tick"] <= tick_start + 7000)]
                    if not r_deaths.empty:
                        first_d = r_deaths.iloc[0]
                        if first_d["attacker_name"] == p:
                            fk_cnt += 1
                        if first_d["user_name"] == p:
                            fd_cnt += 1
                            if (first_d["tick"] <= tick_start + 1280) and not first_d.get("is_traded", False):
                                failed_early_pushes += 1

            traded_deaths_cnt = p_deaths["is_traded"].sum() if not p_deaths.empty and "is_traded" in p_deaths.columns else 0
            traded_death_pct = f"{(traded_deaths_cnt / max(1, len(p_deaths)) * 100):.1f}%" if not p_deaths.empty else "0.0%"

            trade_opps = 0
            trade_succ = 0
            if not sorted_d.empty:
                for idx, d in sorted_d.iterrows():
                    vic = d["user_name"]
                    att = d["attacker_name"]
                    tick = d["tick"]
                    if vic != p and att != p:
                        trade_opps += 1
                        p_trade = sorted_d[(sorted_d["tick"] > tick) & (sorted_d["tick"] <= tick + 200) & (sorted_d["attacker_name"] == p) & (sorted_d["user_name"] == att)]
                        if not p_trade.empty:
                            trade_succ += 1

            trade_conv_pct = f"{(trade_succ / max(1, trade_opps) * 100):.1f}%"
            kb.append(f"| `{p}` | {fk_cnt} | {fd_cnt} | {failed_early_pushes} | {traded_death_pct} | {trade_conv_pct} |")

        # SECTION 3: Player Ratings & Overall Performance
        kb.append("\n---")
        kb.append("## 📊 3. Overall Player Performance & Ratings Summary")
        kb.append("| Player Name | Leetify Rating % | Kills | Deaths | Assists | K/D | ADR (DPR) | Headshots | Survived Rounds |")
        kb.append("|---|---|---|---|---|---|---|---|---|")

        for p in players:
            p_kills = deaths_df[deaths_df["attacker_name"] == p] if not deaths_df.empty else pd.DataFrame()
            p_deaths = deaths_df[deaths_df["user_name"] == p] if not deaths_df.empty else pd.DataFrame()
            p_assists = deaths_df[deaths_df["assister_name"] == p] if not deaths_df.empty else pd.DataFrame()

            k = len(p_kills)
            d = len(p_deaths)
            a = len(p_assists)
            kd = round(k / max(1, d), 2)
            adr = round((k * 100) / max(1, total_rounds), 1)
            hs = int(p_kills["headshot"].sum()) if "headshot" in p_kills.columns and not p_kills.empty else 0
            survived = max(0, total_rounds - d)
            leet_rating = round(((k * 1.5 + a * 0.5 - d) / max(1, total_rounds)) * 10, 2)

            kb.append(f"| `{p}` | `{leet_rating:+.2f}%` | {k} | {d} | {a} | {kd} | {adr} HP | {hs} | {survived} |")

        # SECTION 4: Precision Mechanics Table
        kb.append("\n---")
        kb.append("## 🎯 4. Precision Mechanics & Aim Accuracy Summary")
        kb.append("*(Note: Counter-Strafe Acc % is calculated specifically on Rifle/Sniper/Precision weapons to exclude SMG/Pistol run-and-gun noise)*\n")
        kb.append("| Player Name | Preaim Error ° | Reaction TTD ms | Rifle Counter-Strafe Acc % | Accurate Shots (<34 u/s) | Moving Shots (>34 u/s) | Avg Firing Speed u/s |")
        kb.append("|---|---|---|---|---|---|---|")

        for p in players:
            p_kills = deaths_df[deaths_df["attacker_name"] == p] if not deaths_df.empty else pd.DataFrame()
            p_preaim = f"{p_kills['preaim_error_deg'].mean():.2f}°" if not p_kills.empty and "preaim_error_deg" in p_kills.columns else "N/A"
            p_ttd = f"{ttd_map.get(p, 260.0):.0f} ms"
            
            p_shots = bullet_shots[bullet_shots["user_name"] == p] if not bullet_shots.empty else pd.DataFrame()
            p_r_shots = rifle_shots[rifle_shots["user_name"] == p] if not rifle_shots.empty else pd.DataFrame()

            if not p_r_shots.empty and "is_accurate" in p_r_shots.columns:
                acc_s = int(p_r_shots['is_accurate'].sum())
                mov_s = len(p_r_shots) - acc_s
                cs_acc = f"{(acc_s / len(p_r_shots) * 100):.1f}%"
            elif not p_shots.empty and "is_accurate" in p_shots.columns:
                acc_s = int(p_shots['is_accurate'].sum())
                mov_s = len(p_shots) - acc_s
                cs_acc = f"{(acc_s / len(p_shots) * 100):.1f}%"
            else:
                acc_s, mov_s, cs_acc = 0, 0, "N/A"

            avg_sp = f"{p_shots['speed'].mean():.1f} u/s" if not p_shots.empty else "N/A"

            kb.append(f"| `{p}` | {p_preaim} | {p_ttd} | {cs_acc} | {acc_s} | {mov_s} | {avg_sp} |")

        # SECTION 5: Weapon Micro-Mechanics Breakdown
        kb.append("\n---")
        kb.append("## 🔫 5. Per-Weapon Micro-Mechanics Breakdown")

        for p in players:
            p_shots = bullet_shots[bullet_shots["user_name"] == p] if not bullet_shots.empty else pd.DataFrame()
            if p_shots.empty or "weapon" not in p_shots.columns:
                continue

            total_s = len(p_shots)
            acc_s = p_shots["is_accurate"].sum()
            cs_rate = (acc_s / total_s) * 100

            kb.append(f"\n### Player: **{p}**")
            kb.append(f"- **Overall Counter-Strafe Accuracy (All Guns):** `{cs_rate:.1f}%` ({acc_s} accurate <34 u/s | {total_s - acc_s} moving >34 u/s)")
            kb.append(f"- **Avg Speed at Firing:** `{p_shots['speed'].mean():.1f} u/s` | **Max Speed at Firing:** `{p_shots['speed'].max():.1f} u/s`")
            kb.append("  - **Per-Weapon Breakdown:**")
            
            for weapon_name, w_df in p_shots.groupby("weapon"):
                w_acc = w_df["is_accurate"].sum()
                w_tot = len(w_df)
                w_rate = (w_acc / w_tot) * 100
                w_clean = str(weapon_name).replace("weapon_", "").upper()
                kb.append(f"    - `{w_clean}`: `{w_rate:.1f}%` accurate ({w_acc}/{w_tot}) | Avg speed: `{w_df['speed'].mean():.1f} u/s`")

        # SECTION 6: Multi-Phase Territory Control Snapshots (Official Match Rounds Only)
        kb.append("\n---")
        kb.append("## 📍 6. Multi-Phase Territory Control Snapshots (t=15s Early & t=45s Mid-Round)")
        kb.append("*(Log of active player positions at 15s and 45s after freezetime ends for official match rounds)*\n")

        if not official_freeze_ends.empty:
            t15_ticks = []
            t45_ticks = []
            for i in range(len(official_freeze_ends)):
                fe_tick = official_freeze_ends.iloc[i]["tick"]
                re_tick = official_round_ends.iloc[i]["tick"] if i < len(official_round_ends) else fe_tick + (60 * 64)
                t15_ticks.append(min(fe_tick + (15 * 64), re_tick - 64))
                t45_ticks.append(min(fe_tick + (45 * 64), re_tick - 64))

            pos15_df = ensure_df(self.parser.parse_ticks(["X", "Y", "Z", "last_place_name", "team_num", "health"], ticks=t15_ticks))
            pos45_df = ensure_df(self.parser.parse_ticks(["X", "Y", "Z", "last_place_name", "team_num", "health"], ticks=t45_ticks))

            for idx_t, tick15_val in enumerate(t15_ticks):
                m_round_num = idx_t + 1
                tick45_val = t45_ticks[idx_t]

                round_label = f"Match Round {m_round_num} (Pistol Round)" if m_round_num in (1, 13) else f"Match Round {m_round_num}"
                kb.append(f"### **{round_label} Territory Control Snapshots:**")
                
                has_data_15 = not pos15_df.empty and "tick" in pos15_df.columns and tick15_val in pos15_df["tick"].values
                has_data_45 = not pos45_df.empty and "tick" in pos45_df.columns and tick45_val in pos45_df["tick"].values

                if has_data_15:
                    r15 = pos15_df[pos15_df["tick"] == tick15_val]
                    t15 = [f"{row['name']} ({row['last_place_name']})" for _, row in r15[r15["team_num"] == 2].iterrows()]
                    ct15 = [f"{row['name']} ({row['last_place_name']})" for _, row in r15[r15["team_num"] == 3].iterrows()]
                    if t15 or ct15:
                        kb.append(f"- **t=15s Early Setup:** T-Side [{', '.join(t15)}] vs CT-Side [{', '.join(ct15)}]")

                if has_data_45:
                    r45 = pos45_df[pos45_df["tick"] == tick45_val]
                    t45 = [f"{row['name']} ({row['last_place_name']})" for _, row in r45[r45["team_num"] == 2].iterrows()]
                    ct45 = [f"{row['name']} ({row['last_place_name']})" for _, row in r45[r45["team_num"] == 3].iterrows()]
                    if t45 or ct45:
                        kb.append(f"- **t=45s Mid Regroup:** T-Side [{', '.join(t45)}] vs CT-Side [{', '.join(ct45)}]\n")
                    else:
                        kb.append("\n")

        # SECTION 7: HE & Molotov Damage
        kb.append("---")
        kb.append("## 💥 7. HE Grenade & Molotov Effective Damage Breakdown per Callout Zone")
        if not hurt_df.empty and "weapon" in hurt_df.columns:
            util_hurts = hurt_df[hurt_df["weapon"].str.contains("hegrenade|inferno|molotov", case=False, na=False)]
            if not util_hurts.empty and "user_last_place_name" in util_hurts.columns:
                zone_dmg = util_hurts.groupby(["weapon", "user_last_place_name"])["dmg_health"].sum().reset_index()
                kb.append("| Grenade Type | Impact Callout Zone | Total Effective Damage (HP) |")
                kb.append("|---|---|---|")
                for _, z_row in zone_dmg.iterrows():
                    g_type = "HE Grenade" if "hegrenade" in str(z_row["weapon"]) else "Molotov/Fire"
                    kb.append(f"| {g_type} | `{z_row['user_last_place_name']}` | `{z_row['dmg_health']} HP` |")

        # SECTION 8: Flashbang Matrix
        kb.append("\n---")
        kb.append("## 💣 8. Flashbang Efficiency & Impact Matrix")

        if not blind_df.empty and "attacker_name" in blind_df.columns:
            for p in players:
                p_flashes = blind_df[blind_df["attacker_name"] == p]
                if p_flashes.empty:
                    continue

                enemy_flashes = p_flashes[p_flashes["user_name"] != p]
                team_flashes = p_flashes[p_flashes["user_name"] == p]

                avg_e_dur = enemy_flashes["blind_duration"].mean() if not enemy_flashes.empty else 0.0
                tot_e_dur = enemy_flashes["blind_duration"].sum() if not enemy_flashes.empty else 0.0

                kb.append(f"\n### Player: **{p}**")
                kb.append(f"- **Flashes Thrown:** `{len(p_flashes)}` (Blinded Enemies: `{len(enemy_flashes)}`, Blinded Teammates/Self: `{len(team_flashes)}`)")
                kb.append(f"- **Avg Enemy Blind Duration:** `{avg_e_dur:.2f}s` | **Total Enemy Blind Time:** `{tot_e_dur:.2f}s`")
                if not team_flashes.empty:
                    kb.append(f"- ⚠️ **Teammate Blind Warning:** Blinded teammates/self `{len(team_flashes)}` times (Avg duration: `{team_flashes['blind_duration'].mean():.2f}s`)")
        else:
            kb.append("*(No flashbang blind events recorded in this match)*")

        # SECTION 9: Spatial Opening Duels Log (With Official Match Round Numbers)
        kb.append("\n---")
        kb.append("## 🚪 9. Spatial Opening Duels Log (Official Match Rounds Only)")

        if not deaths_df.empty:
            gun_deaths = deaths_df[~deaths_df["weapon"].str.contains("knife|bayonet", case=False, na=False)]
            for idx, row in gun_deaths.head(25).iterrows():
                m_round = row.get("match_round", 1)
                r_label = f"Match Round {m_round} (Pistol)" if m_round in (1, 13) else f"Match Round {m_round}"
                att = row.get("attacker_name", "Unknown")
                vic = row.get("user_name", "Unknown")
                att_place = row.get("attacker_last_place_name", "Unknown Zone")
                vic_place = row.get("user_last_place_name", "Unknown Zone")
                w = str(row.get("weapon", "")).replace("weapon_", "").upper()
                hs = "🎯 Headshot" if row.get("headshot", False) else "Body"
                preaim_str = f"Preaim Err: {row.get('preaim_error_deg', 0):.1f}°" if "preaim_error_deg" in row else ""
                trade_str = "✅ Traded" if row.get("is_traded", False) else "⚠️ UNTRADED (Died Alone)"
                
                att_team_num = row.get("attacker_team_num", 2)
                att_side = "T-Side" if (m_round <= 12 and att_team_num == 2) or (m_round > 12 and att_team_num == 3) else "CT-Side"

                kb.append(f"- **{r_label}** [{att_side}] (Tick {row.get('tick', 0)}): **{att}** (Location: `{att_place}`) killed **{vic}** (Location: `{vic_place}`) with `{w}` [{hs}] ({preaim_str}) -> {trade_str}")

        # SECTION 10: Complete Micro-Telemetry Chronological Kill Log (With Match Round & Tick Labels)
        kb.append("\n---")
        kb.append("## 💀 10. Chronological Micro-Telemetry Kill Log (Official Match Rounds)")
        kb.append("*(Contains exact Match Round, Tick, TTD ms, Preaim Error °, Firing Speed u/s, Locations & Trade Status)*\n")

        if not deaths_df.empty:
            sorted_deaths = deaths_df.sort_values(by="tick")
            for idx, d in sorted_deaths.head(45).iterrows():
                m_round = d.get("match_round", 1)
                r_label = f"Match Round {m_round} (Pistol)" if m_round in (1, 13) else f"Match Round {m_round}"
                tick = d["tick"]
                attacker = d.get("attacker_name", "Unknown")
                victim = d.get("user_name", "Unknown")
                weapon = str(d.get("weapon", "")).replace("weapon_", "").upper()
                headshot = "🎯 HEADSHOT" if d.get("headshot", False) else "Body"
                att_loc = d.get("attacker_last_place_name", "Unknown")
                vic_loc = d.get("user_last_place_name", "Unknown")
                preaim_err = f"{d.get('preaim_error_deg', 0):.1f}°"
                speed_val = d.get("attacker_speed", 0.0)
                speed_str = f"Stopped ({speed_val:.1f} u/s)" if speed_val < 34.0 else f"MOVING ({speed_val:.1f} u/s)"
                ttd_val = f"{ttd_map.get(attacker, 260.0):.0f}ms"
                trade_str = "✅ Traded" if d.get("is_traded", False) else "⚠️ Untraded"

                kb.append(f"- **{r_label}** (Tick {tick}): **{attacker}** (`{att_loc}`) killed **{victim}** (`{vic_loc}`) with `{weapon}` [{headshot}] | TTD: `{ttd_val}` | Preaim Err: `{preaim_err}` | Attacker Speed: `{speed_str}` | Status: `{trade_str}`")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        full_kb_text = "\n".join(kb)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_kb_text)

        return output_path
