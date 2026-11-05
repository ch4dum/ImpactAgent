# Impact & RWS Spec (Phase 2) — v0.1 draft

สถานะ: **ร่าง รอ owner review** (2026-11-05) · ชื่อที่แสดงให้ผู้ใช้เห็นต้องเป็นของเราเอง (ไม่ใช้ "Swing" ของ FACEIT / ชื่อของ Leetify)

## 0. ชื่อ
| ชื่อ | ใช้ที่ไหน | ความหมาย |
|---|---|---|
| **Impact** | ผู้ใช้เห็น | ค่าเฉลี่ย ΔWP ที่ผู้เล่นได้/เสียต่อรอบ แสดงเป็น `+4.2%` ต่อรอบ (zero-sum) |
| **RWS** | ผู้ใช้เห็น | Round Win Share สูตร ESEA/FACEIT ตรงๆ (§4) |
| `wp`, `delta_wp` | ในโค้ดเท่านั้น | win probability ของฝั่ง T, ส่วนต่างของ wp ต่อ event |

Rating รวม (แบบ 1.70 ของ FACEIT) ยังไม่ทำ จะตัดสินใจหลังมี Impact แล้ว

## 1. แหล่งอ้างอิง (ข้อเท็จจริงที่ยืนยันแล้ว)
- **FACEIT Swing** (matchroom 1-8020514f, `data/validation/dust2-8020514f-faceit.json`):
  - Swing ทั้งแมตช์ = ค่าเฉลี่ยถ่วงจำนวนรอบของ T/CT: ch4dum (5×15.99 + 12×7.21)/17 = 9.79 ✓
  - zero-sum ต่อรอบ: 5 รอบ T ของทีมชนะ ผลรวม +39.15 vs ทีม CT −39.16
  - ผลรวมทีม = ผลจริง − WP ตอนเริ่มรอบ → WP เริ่มรอบเฉลี่ย ≈ 61% (T, ชนะ 5/5) และ ≈ 55% (CT, ชนะ 8/12) ⇒ WP คิด economy ตั้งแต่เริ่มรอบ
  - RWS ทีมชนะรวม 76.47 = 13/17×100, ทีมแพ้ 23.53 = 4/17×100
- **Leetify Rating** (blog "Leetify Rating Explained"): แบ่ง ΔWP ของคิล = killer 35% · damage 30% · flash assist 15% · traded death 20% (ส่วนที่ไม่มี → scale ส่วนที่เหลือขึ้น), death หักเต็มที่คนตาย, หลังจบรอบ: คนรอดฝั่งชนะได้/ฝั่งแพ้เสีย แบ่งเท่ากัน, save ได้ค่าจาก WP รอบถัดไป
- ตัวเลขสัดส่วนเป็นหลักการ ไม่ใช่ข้อมูลของ Leetify → ใช้ได้ เก็บเป็น config

## 2. WP model (v1 = logistic regression)
### 2.1 State snapshot
สร้าง 1 แถวต่อ "สถานะ" ใน `wp_states` (derived, Parquet): ตอน freeze end + หลังทุก event ที่เปลี่ยนสถานะ: kill (รวม suicide/world/team kill), bomb plant, defuse, explode, round end
- `match_id, round_no, tick, event_type, event_ref`
- features (มุมมองฝั่ง T):
  - `t_alive`, `ct_alive`
  - `bomb_planted` (0/1)
  - `time_left_s`: ก่อน plant = เวลารอบที่เหลือ, หลัง plant = เวลาก่อนระเบิด (แยก coefficient ก่อน/หลัง plant ด้วย interaction)
  - `equip_diff_k`: (Σ equip value T ที่ยังรอด − Σ CT ที่ยังรอด)/1000 ณ tick นั้น (อ่านจาก tick data ที่ tick ของ event ไม่ต้องเก็บ tick data ทั้งหมด)
  - `map` (one-hot, ใช้เป็น intercept ประจำแมพ)
- label: `t_won` ของรอบนั้น
- ตัดทิ้ง: warmup, post_match, รอบที่ไม่สมบูรณ์ (ไม่มี winner)

### 2.2 Training
- Logistic regression + L2 regularization (ค่าปรับประจำแมพจะหดเข้าหา 0 เองถ้าข้อมูลน้อย; แมพที่ < 5 แมตช์ตั้งเป็น 0)
- ห้าม pip install เพิ่ม: เช็คก่อนว่า env มี `scikit-learn` / `statsmodels` ไหม ถ้าไม่มีให้เขียน IRLS / gradient descent ด้วย numpy (ไม่กี่สิบบรรทัด)
- weight: ทุกแถวในรอบเดียวกันมี label เดียวกัน → ให้ weight = 1/จำนวนแถวของรอบ (ทุกรอบมีน้ำหนักเท่ากัน)
- บันทึก model เป็น `impactagent/ratings/wp_model_v1.json` (coefficients + feature list + training manifest hash) ไม่ใช้ pickle
- แบ่ง train/test ตาม **แมตช์** (ไม่ใช่ตามแถว)

### 2.2.1 ผล v1 (2026-11-05, `python -m impactagent train-wp data/parsed/wp_states.parquet`)
- ข้อมูล 30 แมตช์ · 639 รอบ · 4,962 แถว trainable · GroupKFold 5 fold ตามแมตช์ · weight = 1/แถว trainable ของรอบ · standardize feature (mean/std เก็บใน JSON, `predict_wp` ใช้ numpy อย่างเดียว) · C จาก {0.01, 0.1, 1, 10} ตาม log loss
- **feature ที่เลือก = ชุด D**: `t_alive, ct_alive, bomb_planted, time_left_pre, time_left_post, equip_diff_k, map_dust2, map_mirage, alive_prod, ct_can_defuse` (C = 1)
  - `ct_can_defuse` = หลัง plant และ C4 เหลือ ≥ 5s ถ้า CT ที่รอดมี kit ไม่งั้น ≥ 10s; **wp_states ยังไม่มีข้อมูล kit → ใช้ ≥ 10s ทุกแถว** (เพิ่ม column `ct_has_kit` ทีหลังได้ `feature_matrix` อ่านให้เองถ้ามี)
- CV (round-weighted, mean ± std):

| ชุด | C | Brier | log loss |
|---|---|---|---|
| baseline (ตาราง t_alive × ct_alive × bomb, smoothing α=2) | – | 0.1638 ± 0.0027 | 0.4955 ± 0.0062 |
| A | 0.1 | **0.1465 ± 0.0030** | **0.4469 ± 0.0092** |
| B (A + map) | 0.1 | 0.1477 ± 0.0032 | 0.4504 ± 0.0092 |
| C (B + alive_prod) | 0.1 | 0.1474 ± 0.0030 | 0.4497 ± 0.0090 |
| **D (C + ct_can_defuse)** | 1 | 0.1472 ± 0.0032 | 0.4491 ± 0.0100 |

- เหตุที่เลือก D ไม่ใช่ A (log loss ต่ำสุด): ต่างกัน 0.002 น้อยกว่า std ระหว่าง fold (~0.009) แต่ใน A `time_left_post` เป็นบวก (C4 เหลือน้อย → WP ของ T ลดลง ผิดทิศ: 2v2 planted 30s 64.8% → 3s 62.4%) ส่วน D แก้ได้ (2v2 planted 12s 59.0% → 8s 91.0%) และ round-start WP ใกล้ FACEIT กว่า (ด้านล่าง). map one-hot ทำให้ CV แย่ลงนิดหน่อย (B > A) แต่ยังเก็บไว้เพราะเป็น intercept ประจำแมพตาม §2.2 และหดเข้าหา 0 อยู่แล้ว
- coefficients ชุด D (standardized / ต่อหน่วย): t_alive +1.40 / +1.017 · ct_alive −0.78 / −0.565 · bomb_planted +0.96 / +2.64 · time_left_pre +0.17 / +0.0047 · time_left_post +0.14 / +0.011 · **equip_diff_k +0.88 / +0.079 (บวก ✓)** · map_dust2 −0.08 · map_mirage −0.16 · alive_prod −0.54 / −0.070 · **ct_can_defuse −0.71 / −1.99** · intercept −0.05
  - ข้อสังเกต: ภายในช่วงที่ CT ยังกู้ทัน (≥ 10s) `time_left_post` ยังบวกเล็กน้อย (30s 63.7% → 12s 59.0%) น่าจะเป็น selection (state ท้าย afterplant ที่ T ยังไม่ชนะมักเป็นตอน CT retake) แต่ขั้นที่ 10s ใหญ่กว่ามาก → โดยรวมเวลาน้อยไม่ทำให้ T แย่ลง; ช่วง 5–10s ที่ CT มี kit จะถูกประเมินสูงไปจนกว่าจะมีข้อมูล kit
- reliability (out-of-fold ชุด D, 10 ช่อง, pred / actual): 0.048/0.045 · 0.146/0.155 · 0.247/0.266 · 0.347/0.348 · 0.448/0.446 · 0.545/0.537 · 0.650/0.635 · 0.748/0.758 · 0.854/0.825 · 0.956/0.955 (ห่างไม่เกิน 0.03 ทุกช่อง)
- sanity (WP ของ T): 5v5 freeze end full buy (equip −2.5k) 44.9% · equip 0 49.8% · 5v4 90s 72.2% > 5v5 90s 46.9% ✓ · 4v4 40s ก่อน plant 45.7% → หลัง plant 67.6% ✓ · eco T (−15k) 23.3% · eco CT (+15k) 76.5% ✓
- **FACEIT round-start WP** (demo 1-8020514f แยก ไม่รวม train, `data/parsed/wp_states_faceit.parquet` สร้างจาก `--faceit-demo`): team_haineieie เป็น T 5 รอบ เฉลี่ย **62.3%** (FACEIT ≈ 61%) · เป็น CT 12 รอบ **54.4%** (FACEIT ≈ 55%) (ชุด A ได้ 64.9% / 52.3%)

### 2.3 ข้อมูล
- `data/train_demos/` (gitignored) + `data/train_demos/manifest.csv` (file, map, source=`faceit|premier|pro`, level, date)
- v1: pub เท่านั้น (FACEIT/Premier), **เริ่ม 30 แมตช์ เป้า 100**, ≥ 5 แมตช์ต่อแมพ, pro ไม่ใช้ใน v1
- **ห้ามเอาแมตช์ validation** (inferno-44a522c3, mirage-65db631a, dust2-85507dfb, dust2-8020514f) มา train: owner ใส่ demo มาได้เลยไม่ต้องคัด โค้ดตัดเองด้วย match fingerprint (map + จำนวนรอบ + สกอร์ + ชุด steam_id) เทียบกับ demo ของ validation pair แล้วรายงานว่าตัดไฟล์ไหน
- parse ครั้งเดียวเก็บ `wp_states` เป็น Parquet แล้วลบ .dem ได้

### 2.4 เช็คคุณภาพ (รายงานจาก CLI)
- Brier score + log loss บน test set เทียบ baseline (ตาราง alive count อย่างเดียว)
- Reliability: แบ่ง WP เป็น 10 ช่อง ช่องละต้องชนะจริงใกล้ค่าที่ทาย
- Sanity: 5v5 เริ่มรอบ full buy ทั้งคู่ ≈ 45–55%, 5v4 > 5v5, plant แล้ว WP ของ T สูงขึ้น, WP เพิ่มตาม equip_diff
- เทียบ WP เริ่มรอบเฉลี่ยกับที่ย้อนคำนวณจาก FACEIT (§1)

## 3. Impact credit
โค้ด: `impactagent/ratings/credit.py` (+ `credit.yaml`), CLI `python -m impactagent impact DEMO [--faceit JSON] [--breakdown]` (รายงานใน `impact_report.py`)

### 3.1 ΔWP ของ event (แยกส่วนเวลาออก, owner 2026-11-05)
ใช้แถวของ `build_wp_states(p)` เป็นลำดับ state ของรอบ: freeze_end → e1 … en → round_end; `wp_start` = WP ของ freeze_end
- `wp_pre(e)` = WP ของ state ก่อนหน้า แต่เลื่อนนาฬิกาไปที่ tick ของ e (`time_left_s` ก่อนหน้า − Δtick/tickrate; `ct_can_defuse` คิดใหม่จากเวลา) · `equip_diff_k` ใช้ของ state ก่อนหน้า · state ก่อนหน้าที่ตัดสินแล้วใช้ rule-fixed
- `delta_time = wp_pre(e) − wp_after(e ก่อนหน้า)` → แถว part/category `time`, steam_id = null (คู่ T +Dt / CT −Dt) ไม่ให้ผู้เล่นคนไหน
- `delta_event = wp_after(e) − wp_pre(e)` → แบ่งตาม §3.2
- round end: `delta = outcome − wp_after(event สุดท้าย)` (ไม่มีส่วนเวลาแยก)
- เหตุผล: model มี `ct_can_defuse` ทำให้ WP กระโดด (เช่น 59% → 91%) ตอน C4 ข้าม 10s ถ้าไม่แยก คน kill ถัดไปจะได้เครดิตของเวลาไปด้วย
- หลัง defuse / explode ทุก state ที่ตามมาในรอบ (เช่น kill หลังระเบิด) ใช้ WP ที่ตัดสินแล้ว (ไม่กลับไปใช้ค่า model)
- ใช้ D แบบมีเครื่องหมาย (มุมมอง T): แถวฝั่ง T รวมกันได้ +D แถวฝั่ง CT ได้ −D ไม่ใช้ |D| (kill อาจทำให้ WP ฝั่งคนฆ่าลดนิดหน่อยได้จาก equip / alive_prod)
- หลาย kill ใน tick เดียว (wp_states รวมเป็น 1 state): แบ่ง delta_event เท่ากันต่อ kill (`multi_kill_same_tick: equal_split`)
- **หน่วย:** `rating_events.delta` เป็น fraction ของการชนะรอบ (0–1) · ×100 ทำจุดเดียวคือ `credit.PCT` ใน `impact_metrics` และตารางของ CLI

### 3.2 การแบ่งเครดิต (config `impactagent/ratings/credit.yaml`)
**Kill** (D ในมุมมองฝั่งคนฆ่า):
| part | สัดส่วนตั้งต้น | ใครได้ |
|---|---|---|
| `kill` | 0.35 | attacker |
| `damage` | 0.30 | ทีมของ attacker (รวม attacker) ตามสัดส่วน damage **แบบ sequential** (`rws._sequential_enemy_damage`: cap ตาม HP ที่เหลือตามลำดับ hit) ใส่เหยื่อในรอบนั้น ณ tick ≤ kill tick ไม่นับ team damage |
| `flash_assist` | 0.15 | `assister_id` ของ kill ที่ `flash_assist = True` ถ้าอยู่ฝั่งเดียวกับ attacker (กฎเดียวกับ `_assists`) |
| `traded_death` | 0.20 | เพื่อนที่ถูกเหยื่อคนนี้ฆ่า แล้ว kill นี้เทรดคืน: `trade_windows` succeeded, teammate = attacker, killer = victim, 0 < tick − death_tick ≤ 4s (หลายคนแบ่งเท่ากัน; ต้อง parse เต็ม ไม่ใช่ fast) |
- ส่วนที่ไม่มีคนได้ → scale ส่วนที่เหลือให้รวม = 1 (เช่น มีแค่ kill + damage → 0.538 / 0.462)
- **ฝั่งคนตาย:** victim เสีย D เต็ม (part `death`)
- team kill / suicide / world (รวม attacker เป็น null): victim เสีย D, ฝั่งตรงข้ามที่ยังรอดได้ D แบ่งเท่ากัน (part `opponent_split`)
- **disconnect** (`by_disconnect`): ไม่ให้ใคร → คู่แถว steam_id null, part/category `disconnect` (นับใน invariant เหมือน time) Impact วัดการเล่น เน็ตหลุดไม่ควรโดนหัก
- **Plant / Explode:** planter (explode = planter คนแรกของรอบ) ได้ D ทั้งหมด, CT ที่รอดเสียแบ่งเท่ากัน · **Defuse:** defuser ได้ D ทั้งหมด, T ที่รอดเสียแบ่งเท่ากัน (ถ้าไม่มีคนรอด ทั้งทีมแบ่ง; ส่วนฝั่งที่เสียของ plant/explode เพิ่มตอน implement เพื่อให้ zero-sum)
- **Round end** (delta ที่เหลือ เช่น หมดเวลา): คนรอดฝั่งชนะได้แบ่งเท่ากัน, คนรอดฝั่งแพ้เสียแบ่งเท่ากัน (ฝั่งไหนไม่มีคนรอด ให้ทั้งทีมฝั่งนั้นแบ่ง)
- **bot:** steam_id null ใน kills → แถวของ bot steam_id null + `is_bot`; attacker ที่เป็น null ถูกนับเป็น suicide/world อยู่แล้ว · ใน `data/parsed/wp_states.parquet` (30 แมตช์ train) มีเหยื่อ id null **0 ครั้ง** (2026-11-05) และ validation 4 แมตช์ 0 แถว bot
- kill หลัง round end / ก่อน freeze end / post_match: ไม่มีแถว (wp_states ใช้เฉพาะ [freeze_end, end])

**Category** (คิดตามเจ้าของแถว ณ tick นั้น; แถว `kill` / `death` / `opponent_split` และ damage ส่วนของ attacker เอง ไล่ลำดับ):
1. `opening_duel`: kill แรกของรอบ (ไม่ใช่ team kill / suicide, กฎเดียวกับ `general_metrics`) — แถวของ attacker และ victim
2. `clutch`: เจ้าของแถวเป็น clutcher (`build_clutches`) ของรอบนั้น และ tick ≥ start_tick (เหยื่อที่ถูก clutcher ฆ่าใช้สถานการณ์ของตัวเอง)
3. `afterplant`: หลัง plant (state ก่อน event) และเจ้าของแถวเป็น T
4. `retake`: หลัง plant และเจ้าของแถวเป็น CT
5. `mid_round_kd`: ที่เหลือ

part อื่น: damage ของเพื่อน (ไม่ใช่ attacker) → `damage_assist` · `flash_assist` → `flash_assist` · `traded_death` → `traded` · `round_end` → `enemy_saving` (ทั้งสองฝั่ง) · plant / explode → `afterplant` (CT ที่เสีย → `retake`) · defuse → `retake` (T ที่เสีย → `afterplant`) · `time` · `disconnect`

### 3.3 Out of scope v1
- คะแนนการ save ปืน (ผลต่อ WP รอบถัดไป) → v2
- HP ใน features → v2
- damage ที่ไม่จบด้วย kill ไม่มีเครดิตตัวเอง (ได้ผ่าน damage share ตอนเหยื่อตายเท่านั้น)
- ข้อมูล defuse kit ใน wp_states (ตอนนี้ `ct_can_defuse` ใช้ ≥ 10s)

### 3.4 Output
- `rating_events` (data-model §2.4) → `data/parsed/<demo>/rating_events.parquet`: 1 แถวต่อ (state, part, ผู้รับ) คอลัมน์ `match_id, round_no, seq, sub, tick, event_type, event_ref, part, steam_id (nullable), is_bot, side, category, delta, wp_pre, wp_after`
- `player_round_ratings.parquet` (match_id, round_no, steam_id, side, rating = Σ delta ของผู้เล่นในรอบ, ไม่รวม time/disconnect) = ค่าของ `player_rounds.rating` (ยังไม่ merge เข้า `build_player_rounds`)
- metric `impact` / `impact_ct` / `impact_t` ใน registry: `aggregation: mean` ต่อรอบที่เล่น, scopes `[all, CT, T]`, `status: custom`, unit `pp` (×100 แล้ว); ข้ามแมตช์ใช้ Σ rating / Σ รอบ · join ใน `compute_match_metrics` (truth ไม่มี key `impact` → ไม่ gate)
- invariant (`check_invariants`, CLI exit 1 ถ้า fail) ต่อรอบ ±1e-9: (ก) Σ แถวฝั่ง T (รวม time/disconnect) = t_won − wp_start (ข) Σ T + Σ CT = 0 (ค) Σ ผู้เล่น/bot ฝั่ง T + Σ time/disconnect ฝั่ง T = (ก) และไม่มีแถว steam_id null นอก time/disconnect/bot · ต่อ state: Σ แถว T = wp_after − wp_pre

### 3.5 ผล v1 (2026-11-05)
- invariant ผ่านทุกรอบ: FACEIT 8020514f 17/17, inferno 13/13, mirage 24/24, dust2-85507dfb 20/20
- เทียบ FACEIT Swing (dust2-8020514f, 10 คน, % ต่อรอบ): Pearson All +0.88 / T +0.92 / CT +0.89 · Spearman All +0.78 / T +0.86 / CT +0.94 · MAE 2.5 / 3.0 / 3.1 pp · ผลรวมทีมชนะ ฝั่ง T ours +38.6 vs FACEIT +39.2, ฝั่ง CT +7.0 vs +11.4 · ลำดับในทีมชนะ ρ 0.90 (สลับแค่ ch4dum/o2donggg), ทีมแพ้ ρ 0.30
- ส่วนที่ไม่มีใครได้ (time) = −4.0 pp ต่อรอบสำหรับ T (เวลาเดินทำให้ T เสีย) ทำให้ผลรวมทีมเราน้อยกว่า FACEIT (ทีมชนะ All +16.3 vs +19.6)

## 4. RWS
- รอบที่ทีมชนะ: 100 แต้มแบ่งตามสัดส่วน damage ใส่ศัตรูในรอบนั้น (ไม่นับ team damage)
- **damage = sequential** ไม่ใช่ `dmg_effective`: แต่ละ hit cap ที่ HP ที่เหลือก่อนโดน (`min(dmg_raw, HP_remaining)`) เรียงตามลำดับ event ต่อ (รอบ, เหยื่อ) ส่วน `dmg_effective` รวม hit ใน tick ที่เหยื่อตายเป็นกลุ่มเดียว ("killing tick = hits รวมกัน = HP ก่อน tick") ซึ่งทำให้ RWS ต่างจาก FACEIT ใน kill tick ที่มีหลาย hit พร้อมกัน (shotgun / หลายคนยิงตายใน tick เดียว)
- team damage ไม่นับเป็นแต้ม แต่ยังลด HP ของเหยื่อในลำดับ sequential (enemy hit ที่ตามหลัง team hit จึงถูก cap ต่ำลง)
- ชนะด้วยระเบิดระเบิด → planter ได้ 30, อีก 70 แบ่งตาม damage · ชนะด้วยการกู้ → defuser ได้ 30, 70 ตาม damage
- รอบที่แพ้ = 0 · ค่าแมตช์ = เฉลี่ยต่อรอบที่เล่น · scopes `[all, CT, T]`
- edge case: ทีมชนะที่ทำ damage รวม 0 (ชนะหมดเวลา/ศัตรู save) → แบ่งเท่ากันในคนที่เล่นรอบนั้น (match นี้เจอ 0 รอบ)
- variant ที่ทดสอบ (2b, mean / max abs err เทียบ FACEIT 30 ช่อง): base `dmg_effective` 0.019/0.094 · ตัด damage หลังรอบจบ 0.029/0.094 (แย่ลง) · cap (attacker,victim,round)=100 0.019/0.094 (ไม่เปลี่ยน) · **sequential 0.002/0.005 ✓ (ตรง 30/30 ±0.01)**
- `status: exact` เมื่อตรง FACEIT ครบ 10 คน × 3 scope (ตอนนี้ 1 แมตช์ 30/30 → ยัง `calibrating`; เลื่อนเป็น exact เมื่อแมตช์ที่ 2 ตรง)

## 5. Validation
| สิ่งที่เช็ค | truth | เกณฑ์ |
|---|---|---|
| RWS | FACEIT dust2-8020514f (All/T/CT) | ตรงทุกช่อง ±0.01 |
| Impact | FACEIT Swing ช่องเดียวกัน | ไม่คาดว่าจะตรง (model ต่างกัน): รายงาน correlation, ลำดับผู้เล่นในทีม, ผลรวมทีม/ฝั่ง, MAE |
| Impact | Leetify `rating-breakdown` ของ 3 pair เดิม (ทำ truth เพิ่มทีหลัง) | เหมือนข้างบน |
| WP | test set + FACEIT round-start WP | §2.4 |
| metric Phase 1 | FACEIT KAST / Entry / Trade / Clutch / MK / accuracy (นิยาม FACEIT อาจไม่เท่า Leetify) | รายงานเท่านั้น ไม่ gate |

## 6. ลำดับงาน (สำหรับ agent ทีละช่วง หยุดรายงานทุกช่วง)
1. เช็ค `.dem.zst`: env มี `zstandard` ไหม (ถ้าไม่มี หยุดถาม owner) แล้ว `inspect` demo FACEIT ได้
2. RWS + validate กับ FACEIT (ง่ายสุด ได้ผลเร็ว)
3. `wp_states` builder + CLI `wp-states DEMO...` (ยังไม่ train)
4. Training + รายงาน §2.4 ✅ (2026-11-05, §2.2.1)
5. Credit assignment + `rating_events` + metric `impact` + invariant tests ✅ (2026-11-05, §3.5)
6. เทียบกับ FACEIT Swing / Leetify, ปรับ config, อัปเดต roadmap
