# Official Leetify V2 Public API Schema & Field Catalogue (for ImpactAgent)

เอกสารนี้รวบรวม **Official Leetify V2 Public API Schema แท้ 100%** ที่ดึงได้โดยตรงจาก Server Endpoint: `https://api-public.cs-prod.leetify.com/v2/matches/{gameId}` สำหรับแมตช์ `f2633f5c-4847-41d2-a481-ebdb665a475a` (13 : 9 on Dust2)

---

## 1. Match Root Object (`LeetifyV2MatchResponse`)

```json
{
  "id": "f2633f5c-4847-41d2-a481-ebdb665a475a",
  "map_name": "de_dust2",
  "finished_at": "2026-08-12T15:00:14.000Z",
  "data_source": "matchmaking",
  "data_source_match_id": "003836584480382911045_0175534288",
  "has_banned_player": false,
  "team_scores": [13, 9],
  "stats": [ /* Array of 10 Player Performance Objects */ ]
}
```

---

## 2. Official V2 Player Performance Schema (`stats[]`)

### A. Core Ratings & Match Impact
| V2 API Field Key | Data Type | Value Sample (ch4dum) | Description |
|---|---|---|---|
| `leetify_rating` | `float` | `0.1085` (+10.85%) | คะแนน Impact รวมทั้งแมตช์ |
| `ct_leetify_rating` | `float` | `0.2280` (+22.80%) | คะแนน Impact ฝั่ง CT |
| `t_leetify_rating` | `float` | `0.0089` (+0.89%) | คะแนน Impact ฝั่ง T |
| `score` | `integer` | `72` | คะแนน Score ในบอร์ด |
| `mvps` | `integer` | `6` | จำนวน MVP |
| `rounds_count` | `integer` | `22` | จำนวนรอบทั้งหมด |
| `rounds_won` | `integer` | `13` | จำนวนรอบที่ชนะ |
| `rounds_lost` | `integer` | `9` | จำนวนรอบที่แพ้ |

---

### B. Aim & Mechanics (`Aim`)
| V2 API Field Key | Data Type | Value Sample (ch4dum) | Description |
|---|---|---|---|
| `preaim` | `float` | `4.9581°` | Crosshair Placement Error (องศา) |
| `reaction_time` | `float` | `0.5859s` (585.9ms) | Time to Damage (เวลาปฏิกิริยา) |
| `accuracy` | `float` | `0.2372` (23.72%) | ความแม่นยำทุกนัดที่ยิง |
| `accuracy_enemy_spotted` | `float` | `0.4061` (40.61%) | ความแม่นยำยิงตอนเห็นศัตรู |
| `accuracy_head` | `float` | `0.2500` (25.00%) | Headshot Accuracy |
| `spray_accuracy` | `float` | `0.3833` (38.33%) | Spray Accuracy นัดที่ 2-10 |
| `counter_strafing_shots_all` | `integer` | `119` | นัดกระสุนที่เช็ค Counter-strafe |
| `counter_strafing_shots_good`| `integer` | `99` | นัดที่ยิงถูกต้องขณะตัวนิ่ง |
| `counter_strafing_shots_bad` | `integer` | `20` | นัดที่ยิงพลาดขณะตัววิ่งอยู่ |
| `counter_strafing_shots_good_ratio`| `float` | `0.8319` (83.19%) | อัตราส่วน Counter-strafe แม่นยำ |
| `shots_fired` | `integer` | `333` | นัดกระสุนที่ยิงทั้งหมด |
| `shots_fired_enemy_spotted`| `integer` | `165` | นัดกระสุนที่ยิงตอนเห็นศัตรู |
| `shots_hit_enemy_spotted` | `integer` | `67` | นัดกระสุนที่ยิงโดนศัตรูตอนเห็น |
| `shots_hit_foe` | `integer` | `79` | จำนวนนัดยิงโดนศัตรูรวม |

---

### C. Combat & General Stats (`General`)
| V2 API Field Key | Data Type | Value Sample (ch4dum) | Description |
|---|---|---|---|
| `total_kills` | `integer` | `33` | จำนวน Kills ทั้งหมด |
| `total_deaths` | `integer` | `15` | จำนวน Deaths ทั้งหมด |
| `total_assists` | `integer` | `4` | จำนวน Assists ทั้งหมด |
| `total_hs_kills` | `integer` | `17` | จำนวน Headshot Kills |
| `kd_ratio` | `float` | `2.20` | อัตราส่วน K/D Ratio |
| `total_damage` | `integer` | `3093` HP | ความเสียหายรวมทั้งเกม |
| `dpr` | `float` | `140.59` HP | Damage per Round (ADR) |
| `kast` | `float` | `0.8636` (86.36%) | KAST Percentage |
| `rounds_survived` | `integer` | `7` | จำนวนรอบที่รอดชีวิต |
| `rounds_survived_percentage`| `float` | `0.3182` (31.82%) | % รอบที่รอดชีวิต |
| `multi1k` / `multi2k` / `multi3k` / `multi4k` / `multi5k` | `integer` | `8 / 1 / 5 / 2 / 0` | รอบที่ทำ Multi-kills (1k-5k) |

---

### D. Trade Efficiency & Positioning (`Trade & Duels`)
| V2 API Field Key | Data Type | Value Sample (ch4dum) | Description |
|---|---|---|---|
| `trade_kill_opportunities` | `integer` | `10` | โอกาสเข้า Trade ทั้งหมด |
| `trade_kill_attempts` | `integer` | `10` | พยายามเข้า Trade |
| `trade_kills_succeed` | `integer` | `6` | Trade คิลสำเร็จ |
| `trade_kill_attempts_percentage` | `float` | `1.0000` (100%) | % พยายามเข้า Trade |
| `trade_kills_success_percentage` | `float` | `0.6000` (60%) | % อัตราสำเร็จในการ Trade |
| `trade_kill_opportunities_per_round` | `float` | `0.5263` | โอกาส Trade เฉลี่ยต่อรอบ |
| `traded_death_opportunities` | `integer` | `5` | โอกาสที่เพื่อนจะ Trade ให้เมื่อตนเองตาย |
| `traded_death_attempts` | `integer` | `2` | จำนวนครั้งที่พยายามให้เพื่อน Trade |
| `traded_deaths_succeed` | `integer` | `1` | จำนวนครั้งที่ตายแล้วเพื่อน Trade ได้สำเร็จ |
| `traded_death_attempts_percentage` | `float` | `0.4000` (40%) | % พยายามให้เพื่อน Trade |
| `traded_deaths_success_percentage` | `float` | `0.5000` (50%) | % เพื่อน Trade คืนสำเร็จ |
| `traded_deaths_opportunities_per_round` | `float` | `0.2632` | โอกาสให้เพื่อน Trade เฉลี่ยต่อรอบ |

---

### E. Utility Usage & Flashbang Impact (`Utility`)
| V2 API Field Key | Data Type | Value Sample (ch4dum) | Description |
|---|---|---|---|
| `he_thrown` | `integer` | `7` | จำนวน HE Grenades ที่โยน |
| `he_foes_damage_avg` | `float` | `18.00` HP | Damage ใส่ศัตรูเฉลี่ยต่อลูก HE |
| `he_friends_damage_avg` | `float` | `0.1429` HP | Damage ใส่เพื่อนเฉลี่ยต่อลูก HE |
| `molotov_thrown` | `integer` | `14` | จำนวน Molotov ที่โยน |
| `smoke_thrown` | `integer` | `15` | จำนวน Smoke Grenades ที่โยน |
| `flashbang_thrown` | `integer` | `22` | จำนวน Flashbang ที่โยน |
| `flashbang_hit_foe` | `integer` | `12` | ศัตรูที่โดน Flashbang ตาบอด |
| `flashbang_hit_friend` | `integer` | `12` | เพื่อนที่โดน Flashbang ตาบอด |
| `flashbang_hit_foe_avg_duration`| `float` | `2.88s` | วินาทีศัตรูตาบอดเฉลี่ยต่อคน |
| `flashbang_leading_to_kill` | `integer` | `1` | จำนวน Flash ที่นำไปสู่การฆ่า |
| `flash_assist` | `integer` | `2` | Flash Assists |
| `utility_on_death_avg` | `float` | `$225.00` | มูลค่าระเบิด ($) เฉลี่ยที่ถือตาย |

---

## 3. Dedicated Sub-Endpoints Summary

1. `GET /api/games/{gameId}/opening-duels`:
   * รายการ Opening Duels รายรอบ (มี `tick`, `round`, `roundTime`, `traded`, `attackerName`, `victimName`, `attackerWeapon`)
2. `GET /api/games/{gameId}/clutches`:
   * รายการ Clutch รายรอบ (มี `roundNumber`, `handicap` 1v1 ถึง 1v5, `attempts`, `clutchesWon`, `startedWithTrade`)
