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

**Storage:** ตาราง summary (matches, match_players + metric jsonb, rounds, player_rounds) อยู่ใน **Postgres** (Supabase) ส่วน event ทุกชนิด (รวม kills, shots, damages, engagements, rating_events …) อยู่ใน **Parquet ต่อแมตช์** บน R2 แล้ว query ด้วย DuckDB ตอนต้องการ (ถูกและเร็วกว่าเอา shot เป็นแสนแถวต่อแมตช์ไปใส่ Postgres) · ตารางไหนอยู่ที่ไหน + layout ใน R2: [`backend.md`](backend.md) §2.2, §3

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
| ct_buy_type, t_buy_type | `pistol` · `eco` · `semi-eco` · `force` · `full` (เกณฑ์: pistol = รอบแรกของแต่ละครึ่ง/OT, eco < $1,500, semi-eco $1,500–2,499, force $2,500–3,899, full ≥ $3,900) |

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
| rating | Impact ของรอบ = Σ `rating_events.delta` ของผู้เล่น (fraction, รวมส่วน time ของ survivors, ไม่รวม disconnect) ตอนนี้อยู่ใน `player_round_ratings.parquet` |

### 2.3 Event level (Parquet)
**`kills`** (Parquet อย่างเดียว ไม่ลง Postgres: owner 2026-11-06, backend.md §0)
match_id, round_no, tick, round_time, attacker_id, victim_id, assister_id, **flash_assist** (bool: ตอนเป็น True `assister_id` คือคน flash; ยังไม่มีคอลัมน์ `flash_assister_id`), weapon, headshot, wallbang, through_smoke, noscope, attacker_blind, attacker_side, victim_side, is_team_kill, **attacker_xyz, victim_xyz, attacker_place, victim_place**, is_suicide (attacker null หรือ = victim), is_opening / traded_by_kill_tick / is_trade_kill (**ยังไม่เป็นคอลัมน์**: opening คิดใน `general_metrics`, trade จาก `trade_windows`), **post_match** (death หลัง `cs_win_panel_match` เช่น world suicide ตอนขึ้น scoreboard: ทุก metric ต้องกรองทิ้ง ยกเว้นตัวหารของ unused utility), **by_disconnect** (suicide/world ที่ tick เดียวกับ `player_disconnect` ของคนตาย: ยังนับเป็น death ใน General แต่ clutch outcome ไม่นับว่าตาย)

**`damages`**: match_id, round_no, tick, attacker_id, victim_id, weapon, hitgroup, dmg_raw, **dmg_effective** (HP ที่หายจริง: cap ที่ HP ที่เหลือ และทุก hit ใน tick ที่ฆ่ารวมกัน = HP ที่เหลือก่อน tick นั้น; HE damage ใน metric utility ใช้ dmg_raw), dmg_armor, victim_hp_after, is_team, attacker_side, victim_side, **attacker_place, victim_place, attacker_xyz, victim_xyz**

**`death_inventory`**: match_id, tick, steam_id, inventory (list ชื่อ item), active_weapon. หนึ่งแถวต่อการตาย (เฉพาะคนที่ตาย ณ tick นั้น อ่านจาก tick − 1). ใช้คิด unused utility

**`shots`**: match_id, round_no, tick, shooter_id, weapon, **weapon_class** (`rifle` · `sniper` · `smg` · `pistol` · `shotgun` · `mg` · `melee` · `other`), **speed_2d**, ducking, scoped, **died_this_tick**, **aim_shot** (นัดที่นับใน accuracy: ปืน + taser ไม่ใช่ลูกซอง ไม่ใช่ tick ที่คนยิงตาย), hit, hit_head (ทุก hurt ของนัดเป็นหัว), hit_victim_id (nullable), enemy_spotted (visibility), **spray_id**, shot_index_in_spray, spray_len, first_bullet, engagement_id (nullable). (pitch / yaw / xyz ยังไม่เก็บ)

**`grenades`**: match_id, round_no, entity_id, thrower_id, type (`flash`/`smoke`/`he`/`molotov`/`incendiary`/`decoy`), throw_tick, detonate_tick, detonate_xyz, detonate_place

**`smokes`** (visibility): match_id, round_no, entity_id, thrower_id, detonate_tick, expire_tick (`smokegrenade_expired` ตัวแรกของ entity เดียวกันหลังระเบิด ถ้าไม่มี = ระเบิด + 22.06s), x, y, z

**`blinds`**: match_id, round_no, tick, grenade_entity_id, thrower_id, victim_id, duration, is_teammate

**`bomb_events`**: match_id, round_no, tick, steam_id, type (`plant`/`defuse_start`/`defuse`/`explode`), site

### 2.4 Derived
**`player_zones`**: steam_id, side (`CT`/`T`), zone (`last_place_name`), kills, deaths (สรุปการฆ่าและการตายต่อผู้เล่นแยกตามโซนและฝั่ง)

**`engagements`** (A → B ครั้งหนึ่ง)
| column | หมายเหตุ |
|---|---|
| engagement_id | |
| match_id, round_no, attacker_id, victim_id | |
| first_seen_tick | จาก visibility module: สแกนย้อนจาก damage ทีละ tick ขณะ A เห็น B (gap ≤ 8 tick) สูงสุด 2.5s; null = ยังเห็นอยู่ที่ขอบ (≥ 2.5s) |
| first_damage_tick, last_damage_tick | |
| kill_tick | nullable |
| ttd_ms | first_damage − first_seen |
| ttk_ms | kill − first_seen (nullable) |
| crosshair_err_deg | มุมระหว่าง view ตอน first_seen กับตอน first_damage |
| shots, hits | shots = นัดของ A ตั้งแต่ first_seen ถึง damage สุดท้าย, hits = tick ที่ทำ damage |
| outcome | v1: `kill` · `damaged` (ยังไม่สร้าง engagement ที่ไม่มี damage: `no_damage` · `died` ทีหลัง) |
| attacker_place, victim_place | ยังไม่ทำ |

**`trade_windows`**: match_id, round_no, death_tick, dead_id, killer_id, teammate_id, had_opportunity, attempted, succeeded (1 แถวต่อ teammate ที่ยังรอด ใช้ทั้ง Trade Kill และ Traded Death). Parser เก็บ feature ที่ sample จาก tick ใน window (ไม่เก็บ tick data): dist_to_victim, dist_to_killer, min_dist_to_killer, teammate_spotted_killer, killer_spotted_teammate, min_aim_angle_spotted, damaged_killer, fired, succeeded. `had_opportunity` / `attempted` คิดใน metrics (นิยามยังเป็นสมมติฐาน, spec §3)

**`clutches`**: match_id, round_no, steam_id, side, vs_n, start_tick, kills, outcome (`won`/`lost`/`saved`) (derive จาก kills + player_rounds_side + rounds ไม่ต้อง parse ใหม่)

**`wp_states`** (impact-spec §2.1, Parquet `data/parsed/wp_states.parquet` สำหรับ train; สร้างใหม่ทุกครั้งใน `build_rating_events`): 1 แถวต่อ state (freeze_end, kill, plant, defuse, explode, round_end) · ข้อมูลจาก tick อ่านเฉพาะ state tick (และ tick − 1 สำหรับ `ct_defusing_pre`) ไม่เก็บ tick data
| column | dtype | หมายเหตุ |
|---|---|---|
| match_id, map, round_no, tick | string, string, int64, int64 | |
| event_type, event_ref | string | |
| t_alive, ct_alive | int64 | นับจาก kills หลัง event |
| bomb_planted | int8 | |
| time_left_s | float64 | ก่อน plant = เวลารอบที่เหลือ, หลัง plant = เวลาก่อน C4 ระเบิด |
| equip_diff_k | float64 | (Σ equip T − CT ที่รอด)/1000 |
| ct_has_kit | bool | CT ที่รอดหลัง event ≥ 1 คนมี `has_defuser` |
| ct_defusing | bool | มี defuse ที่กำลังกู้และจะทันเวลา หลัง event (`is_defusing` ณ tick) |
| ct_defusing_pre | bool | เหมือน `ct_defusing` แต่ก่อน event (tick − 1); credit ใช้เป็น wp_pre |
| t_won | int8 | label |
| trainable | bool | false = WP ตายตัวตามกฎ (round_end, defuse, explode, ฝั่งหนึ่งตายหมด) |

**`rating_events`** (impact-spec §3, Parquet `data/parsed/<demo>/rating_events.parquet`, ใช้ทำ Rating Breakdown): 1 แถวต่อ (state, part, ผู้รับ)
| column | dtype | หมายเหตุ |
|---|---|---|
| match_id | string | |
| round_no, seq, sub | int64, int32, int8 | seq = ลำดับ state ในรอบ (wp_states), sub = ลำดับ kill ใน tick เดียวกัน |
| tick | int64 | |
| event_type, event_ref | string | `kill` · `plant` · `defuse` · `explode` · `round_end` (ref จาก wp_states) |
| part | string | `kill` · `damage` · `flash_assist` · `traded_death` · `death` · `opponent_split` · `plant` · `defuse` · `explode` · `round_end` · `time` · `disconnect` |
| steam_id | string, nullable | null = `disconnect` / bot / `time` เฉพาะเมื่อ `time_credit: none` (default `survivors` ให้คนรอด) |
| is_bot | bool | |
| side | string | `T`/`CT` (แถวที่ steam_id null มาเป็นคู่ T +D / CT −D) |
| category | string | `opening_duel` · `mid_round_kd` · `clutch` · `afterplant` · `retake` · `damage_assist` · `flash_assist` · `traded` · `enemy_saving` · `time` · `disconnect` |
| delta | float64 | **fraction** ของการชนะรอบ มุมมองฝั่งของแถว (×100 ทำที่ `impact_metrics` เท่านั้น) |
| wp_pre, wp_after | float64 | WP ของ T ก่อน/หลัง event (debug + invariant) |

Key: (match_id, round_no, seq, sub, part, side, steam_id). `player_round_ratings.parquet` (match_id, round_no, steam_id, side, rating) = `player_rounds.rating`

**`state_ticks`** (Phase 3.1, `snapshot/p1/state_ticks.parquet`, backend.md §6.2): แถวดิบของ `parse_ticks` ณ state ticks ∪ bomb_begindefuse ticks และ tick − 1 × ผู้เล่น: tick, steamid, name, team_num, current_equip_value, has_defuser, is_defusing, **balance** (เงินในมือ, ไว้ใช้กับ WP / economy รุ่นหน้า), is_alive, health, armor_value, has_helmet, active_weapon_name, X, Y, Z (`wp_states.STATE_TICK_PROPS`) · คู่กับ `defuse_starts` (tick, sid, kind begin/abort, haskit), `cvars` (server_cvar ทุกแถว) และ `header.json` → สร้าง `wp_states` ใหม่ได้โดยไม่ต้องมี demo

**`replay`** (Phase 3.1b, ยังไม่ implement, backend.md §6.3): ตำแหน่ง/ทิศ/HP/อาวุธ 8 Hz ต่อผู้เล่น 1 ไฟล์ต่อรอบ + เส้นทางระเบิด (ข้อยกเว้นของหลัก §1.1)

### 2.5 Metric values
ค่า metric ต่อผู้เล่นต่อแมตช์มี 2 รูป ข้อมูลเดียวกัน (owner 2026-11-06, backend.md §2.1)

**Postgres: `match_players.metrics`** (jsonb, 1 แถวต่อผู้เล่นต่อแมตช์) ใช้กับหน้าเว็บและ profile
```json
{"all": {"adr": [value, numerator, denominator], "ttd": [value, null, null], ...}, "CT": {...}, "T": {...}}
```
- key = `id` ใน registry ทุกตัว · `CT` / `T` ใส่เมื่อ `compute_match_metrics` คิดแยกฝั่งได้ (ตอนนี้มีแค่ `all`)
- รวมข้ามแมตช์ = Σnumerator / Σdenominator (§1.3) · median metric คิดจาก `engagements` (§1.4)
- เหตุผลที่ไม่ใช้ long ใน PG: ~1.7k แถว/แมตช์ (~300 KB) ทำให้ Supabase free 500 MB จุได้ ~1.4k แมตช์; jsonb ~10 แถว/แมตช์ → ~6k แมตช์

**Parquet: `metric_values.parquet`** (long format, 1 แถวต่อ metric ต่อผู้เล่นต่อ scope) ใช้กับ LLM tool / DuckDB
| column | หมายเหตุ |
|---|---|
| match_id, steam_id, metric_id | |
| scope | `all` · `CT` · `T` (ต่อยอดเป็น economy ได้) |
| value | ค่าที่แสดง |
| numerator, denominator | null สำหรับ median metric |

→ column chooser, การ์ด metric, profile trend และ LLM tool ใช้ค่าชุดเดียวกัน (registry เดียวกัน)

---

## 3. หน้า → ตาราง (เช็คว่าไม่ขาด)

| หน้า Leetify | ตารางที่ใช้ |
|---|---|
| Overview / scoreboard / column chooser | match_players.metrics (metric_values) + registry |
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
| 2D Replay | replay (8 Hz, Phase 3.1b) |

---

## 4. Metric Registry

นิยามของ metric ทุกตัวอยู่ในไฟล์เดียว (`impactagent/metrics/registry.yaml`) ใช้ร่วมกันทั้ง parser, API, UI และ LLM coach. `id` = ชื่อคอลัมน์ใน `compute_match_metrics()` และ key ใน truth file; ตรวจด้วย `impactagent/metrics/registry.py` (`validate-all` เรียกให้)

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
- **Parse safety:** .dem หลังแตก ≤ 1 GiB (หยุดแตกทันทีถ้าเกิน), parse ใน child process ที่ถูก kill เมื่อเกิน 300s; ไฟล์ temp ลบทุกกรณี (`impactagent/constants.py`)

## 6. Visibility
`impactagent/visibility/`: `VisibilityBackend.sees(states, tick, observer, target)` สลับ backend ได้ (`spotted` / `raycast`). อ่าน state เฉพาะ tick ที่ query ต้องใช้ (`TickStates`) แล้วทิ้ง ไม่เก็บ tick data. Raycast: ตา = Z + 64 + `m_flDuckViewOffset` → จุดเป้า 8 จุดบนตัว (`TARGET_LAYOUT`), เป้าในตำแหน่งใดก็ได้ใน 7 tick ล่าสุด (lag), ไม่ผ่านควัน (`smokes`), อยู่ใน FOV 50° จากทิศที่มอง. เป้าที่ตายใน tick นั้นใช้ state ของ tick ก่อนหน้า. ค่าคงที่อยู่ใน `constants.py`

## 7. ยังไม่ตัดสินใจ
- Trade window: ช่วง [3.48, 4.47) s ใช้ 4.0 (spec §3); นิยาม trade opportunity / attempt รอ visibility
- ~~Postgres แบบ self-host หรือ Supabase~~ → **Supabase** (owner 2026-11-06): schema, RLS, R2 layout, jobs อยู่ใน [`backend.md`](backend.md)
- Scope `CT` / `T` ของ metric (§2.5) รอ `compute_match_metrics` คิดแยกฝั่ง
