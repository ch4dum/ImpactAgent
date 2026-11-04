# Data Model v0.1

โครงข้อมูลหลักของ ImpactAgent เป้าหมายคือ **ทุกหน้าที่เห็นใน Leetify ต้องสร้างได้จากตารางชุดนี้** (ดู [`../research/leetify-sitemap.md`](../research/leetify-sitemap.md)) และ LLM coach ต้อง query ข้อมูลชุดเดียวกันได้

> v0.1 = พอให้เริ่มเขียน parser ได้ รายละเอียด (index, partition, type) จะปรับตอน implement

---

## 1. หลักการ

1. **เก็บ event ไม่เก็บ tick:** หลัง parse เสร็จเก็บแค่ event (kill, damage, shot …) กับข้อมูลที่สรุปแล้ว ไม่เก็บตำแหน่งราย tick (179MB → ไม่กี่ MB ต่อแมตช์) ยกเว้นตอนทำ 2D Replay ในอนาคต
2. **Engagement เป็นหน่วยกลาง:** "การดวล" (ช่วงที่ A เห็น B จนถึง damage/kill/หายไป) เป็นฐานของ Aim (TTD, crosshair placement), Head to Head และ Map Zones
3. **Metric เก็บเป็น numerator/denominator:** ห้ามเฉลี่ย % ข้ามแมตช์ตรงๆ (เฉลี่ยของ % ≠ % รวม) ต้องรวม numerator และ denominator ก่อนแล้วค่อยหาร
4. **Metric ที่เป็น median** (TTD, crosshair placement) รวมข้ามแมตช์ด้วยการหารไม่ได้ → คำนวณจากตาราง `engagements` ตรงๆ
5. **ทุกตารางมี `match_id` และ `round_no`** เพื่อ filter ตาม side/economy/phase ได้ทุกหน้า
6. **ผู้เล่นใช้ `steam_id` (Steam64)** เป็น key ส่วนชื่อเปลี่ยนได้ เก็บชื่อที่ใช้ในแมตช์นั้นไว้แยก

**Storage:** ตาราง core (matches → player_rounds, kills, metric_values) อยู่ใน **Postgres** ส่วน event ละเอียด (shots, damages, engagements …) อยู่ใน **Parquet ต่อแมตช์** บน object storage แล้ว query ด้วย DuckDB ตอนต้องการ (ถูกและเร็วกว่าเอา shot เป็นแสนแถวต่อแมตช์ไปใส่ Postgres)

---

## 2. ตาราง

### 2.1 Match level
**`matches`**
| column | type | หมายเหตุ |
|---|---|---|
| match_id | uuid | PK |
| source | text | `upload` · `matchmaking` · `faceit` |
| demo_sha256 | text | กันอัปไฟล์ซ้ำ |
| map | text | `de_dust2` |
| played_at | timestamptz | |
| tickrate | int | |
| rounds_played | int | ไม่รวม warmup/knife |
| score_a / score_b | int | team A = ทีมที่เริ่มฝั่ง CT |
| winner | text | `a` · `b` · `draw` |
| parse_version | text | ใช้ re-parse เมื่อสูตรเปลี่ยน |

**`match_players`**: match_id, steam_id, name, team (`a`/`b`), premier_rating (nullable), crosshair_code (nullable)

### 2.2 Round level
**`rounds`**
| column | หมายเหตุ |
|---|---|
| match_id, round_no | PK, เริ่มที่ 1 |
| start_tick, freeze_end_tick, end_tick | `round_time` ทุกที่ = (tick − freeze_end_tick) / tickrate |
| ct_team, t_team | `a`/`b` (สลับตอนครึ่งเวลา/OT) |
| winner_side | `CT`/`T` |
| win_reason | `elimination` · `bomb_exploded` · `defused` · `time` |
| plant_tick, plant_site | nullable, ใช้แยก pre-plant/post-plant |
| ct_equip_value, t_equip_value | มูลค่าอุปกรณ์ตอน freeze end |
| ct_buy_type, t_buy_type | `pistol` · `eco` · `semi_eco` · `force` · `full` |

**`player_rounds`** (1 แถวต่อผู้เล่นต่อรอบ เป็นฐานของ General, KAST, economy split)
| column | หมายเหตุ |
|---|---|
| match_id, round_no, steam_id | PK |
| side | `CT`/`T` |
| equip_value, money_start | |
| kills, deaths, assists, flash_assists | |
| damage | capped ที่ HP ที่เหลือของเหยื่อ |
| survived, was_traded | bool |
| kast | bool (K or A or S or T) |
| unused_utility_value | มูลค่าระเบิดที่ถือตอนตาย (null ถ้ารอด) |
| rating | Impact rating ของรอบ (เฟสหลัง) |

### 2.3 Event level (Parquet)
**`kills`** (เก็บใน Postgres ด้วย เพราะใช้บ่อย)
match_id, round_no, tick, round_time, attacker_id, victim_id, assister_id, flash_assister_id, weapon, headshot, wallbang, through_smoke, noscope, attacker_blind, attacker_side, victim_side, is_team_kill, **attacker_xyz, victim_xyz, attacker_place, victim_place**, is_opening, **traded_by_kill_tick** (nullable), is_trade_kill, **post_match** (death หลัง `cs_win_panel_match` เช่น world suicide ตอนขึ้น scoreboard: ทุก metric ต้องกรองทิ้ง ยกเว้นตัวหารของ unused utility)

**`damages`**: match_id, round_no, tick, attacker_id, victim_id, weapon, hitgroup, dmg_raw, **dmg_effective** (HP ที่หายจริง: cap ที่ HP ที่เหลือ และทุก hit ใน tick ที่ฆ่ารวมกัน = HP ที่เหลือก่อน tick นั้น; HE damage ใน metric utility ใช้ dmg_raw), dmg_armor, victim_hp_after, is_team

**`death_inventory`**: match_id, tick, steam_id, inventory (list ชื่อ item), active_weapon. หนึ่งแถวต่อการตาย (เฉพาะคนที่ตาย ณ tick นั้น อ่านจาก tick − 1). ใช้คิด unused utility

**`shots`**: match_id, round_no, tick, shooter_id, weapon, pitch, yaw, xyz, **speed_2d**, ducking, scoped, **spray_id**, shot_index_in_spray, enemy_spotted, hit_victim_id (nullable), engagement_id (nullable)

**`grenades`**: match_id, round_no, entity_id, thrower_id, type (`flash`/`smoke`/`he`/`molotov`/`incendiary`/`decoy`), throw_tick, detonate_tick, detonate_xyz, detonate_place

**`blinds`**: match_id, round_no, tick, grenade_entity_id, thrower_id, victim_id, duration, is_teammate

**`bomb_events`**: match_id, round_no, tick, steam_id, type (`plant`/`defuse_start`/`defuse`/`explode`), site

### 2.4 Derived
**`engagements`** (A → B ครั้งหนึ่ง)
| column | หมายเหตุ |
|---|---|
| engagement_id | |
| match_id, round_no, attacker_id, victim_id | |
| first_seen_tick | จาก visibility module |
| first_damage_tick | nullable |
| kill_tick | nullable |
| ttd_ms | first_damage − first_seen |
| crosshair_err_deg | มุมระหว่าง view ตอน first_seen กับตอน first_damage |
| shots, hits | |
| outcome | `kill` · `damaged` · `no_damage` · `died` |
| attacker_place, victim_place | |

**`trade_windows`**: match_id, round_no, death_tick, dead_id, killer_id, teammate_id, had_opportunity, attempted, succeeded (1 แถวต่อ teammate ที่ยังรอด ใช้ทั้ง Trade Kill และ Traded Death)

**`clutches`**: match_id, round_no, steam_id, vs_n, start_tick, kills, outcome (`won`/`lost`/`saved`)

**`rating_events`**: match_id, round_no, tick, steam_id, category (`mid_round_kd` · `opening_duel` · `retake` · `clutch` · `damage_assist` · `traded` · `flash_assist` · `afterplant` · `enemy_saving`), delta (ใช้ทำ Rating Breakdown)

### 2.5 Metric values
**`metric_values`** (long format, 1 แถวต่อ metric ต่อผู้เล่นต่อ scope)
| column | หมายเหตุ |
|---|---|
| match_id, steam_id, metric_id | |
| scope | `all` · `CT` · `T` (ต่อยอดเป็น economy ได้) |
| value | ค่าที่แสดง |
| numerator, denominator | null สำหรับ median metric |

→ column chooser, การ์ด metric, profile trend และ LLM tool อ่านจากตารางเดียวกันได้หมด

---

## 3. หน้า → ตาราง (เช็คว่าไม่ขาด)

| หน้า Leetify | ตารางที่ใช้ |
|---|---|
| Overview / scoreboard / column chooser | metric_values + registry |
| General | player_rounds, kills |
| Timeline | player_rounds (สะสมรายรอบ), rounds (economy) |
| Aim | shots, damages, engagements |
| Utility | grenades, blinds, damages, player_rounds |
| Activity | damages, shots, player_rounds |
| Trades | trade_windows |
| Opening Duels | kills (is_opening) |
| Clutches | clutches |
| Head to Head | engagements, kills, damages, blinds (กรองคู่ attacker↔victim) |
| Rating Breakdown | rating_events, player_rounds.rating |
| Map Zones | kills (place, xyz) + rounds (side, plant_tick, buy_type) |
| Your Match | metric_values (แมตช์นี้ vs 30 แมตช์ล่าสุด) |
| Profile / Aim / Utility (หลายแมตช์) | metric_values (รวม num/den), engagements (median) |
| 2D Replay | ❌ ต้องมี tick data (ยังไม่เก็บ) |

---

## 4. Metric Registry

นิยามของ metric ทุกตัวอยู่ในไฟล์เดียว (`impactagent/metrics/registry.yaml`) ใช้ร่วมกันทั้ง parser, API, UI และ LLM coach

| field | ความหมาย |
|---|---|
| `id` | key ถาวร เช่น `ttd` |
| `label` | ชื่อที่แสดง (เป็นชื่อของเราเอง ไม่ใช้ชื่อ Leetify ตรงๆ) |
| `category` | `rating` · `general` · `aim` · `positioning` · `utility` |
| `unit` / `format` | `ms`, `%`, `deg`, `hp` … + วิธีแสดง |
| `direction` | `higher_better` · `lower_better` · `neutral` |
| `aggregation` | `ratio` (Σnum/Σden) · `median` · `sum` · `mean` |
| `numerator` / `denominator` | อธิบายว่านับอะไร |
| `source` | ตาราง + เงื่อนไข |
| `scopes` | `[all, CT, T]` |
| `benchmark` | แหล่ง benchmark (ใส่ทีหลัง) |
| `coach_hint` | คำอธิบายสั้นๆ ให้ LLM ใช้: metric นี้บอกอะไร ฝึกยังไง |
| `ref` | ลิงก์ไปหัวข้อใน `docs/metrics/` |
| `status` | `exact` · `calibrating` · `custom` |

**ตัวอย่าง**
```yaml
- id: adr
  label: Damage per Round
  category: general
  unit: hp
  direction: higher_better
  aggregation: ratio
  numerator: sum of effective damage to enemies
  denominator: rounds played
  source: player_rounds.damage
  scopes: [all, CT, T]
  status: exact

- id: ttd
  label: Time to Damage
  category: aim
  unit: ms
  direction: lower_better
  aggregation: median
  source: engagements.ttd_ms WHERE ttd_ms < 1000
  coach_hint: เวลาจากเห็นศัตรูถึงทำ damage ได้ ถ้าสูง มักมาจาก crosshair placement ไม่ดีหรือ peek แบบไม่พร้อม
  status: calibrating

- id: counter_strafe_pct
  label: Counter-Strafing
  category: aim
  unit: pct
  direction: higher_better
  aggregation: ratio
  numerator: rifle shots at spotted enemy with speed_2d < 0.34 × weapon max speed
  denominator: rifle shots at spotted enemy, not ducking
  source: shots
  status: exact

- id: enemies_flashed_per_flash
  label: Enemies Flashed per Flash
  category: utility
  unit: ratio
  direction: higher_better
  aggregation: ratio
  numerator: enemy blinds with duration > 1.1s
  denominator: flashbangs thrown
  source: blinds, grenades
  status: exact

- id: trade_kill_success
  label: Trade Kill Success
  category: positioning
  unit: pct
  direction: higher_better
  aggregation: ratio
  numerator: trade_windows.succeeded
  denominator: trade_windows.attempted
  source: trade_windows
  status: calibrating
```

---

## 5. Pipeline

```
.dem ──▶ parse (demoparser2) ──▶ event tables ──▶ derive (engagements, trades, clutches, rating) ──▶ metric_values
                                      │                                                              │
                                      └────────── Parquet (R2) ──────────┐          Postgres ◀───────┘
                                                                         ▼
                                                    LLM coach (tools + read-only SQL / DuckDB)
```
- แต่ละขั้นเป็น function แยก ทดสอบได้เดี่ยวๆ และ re-run ตั้งแต่ขั้น derive ได้โดยไม่ต้อง parse ใหม่ เมื่อสูตรเปลี่ยน
- `parse_version` บอกว่าแมตช์ไหนต้องคำนวณใหม่

## 6. ยังไม่ตัดสินใจ
- Visibility module: spotted mask ก่อน → raycast ทีหลัง (ดู `metrics/leetify-metrics-spec.md` ข้อ 0)
- Trade window กี่วินาที (calibrate ด้วย `data/validation/`)
- เกณฑ์ buy type (มูลค่าอุปกรณ์เท่าไหร่ = eco/force/full)
- Postgres แบบ self-host หรือ Supabase
