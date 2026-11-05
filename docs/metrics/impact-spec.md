# Impact & RWS Spec (Phase 2) — v0.1 draft

สถานะ: **v1 — Phase 2 ปิดแล้ว** (2026-11-05) · WP model v2 (kit + defuse ที่กำลังกู้) ใช้งานตั้งแต่ 2026-11-06 (§2.2.2) · ชื่อที่แสดงให้ผู้ใช้เห็นต้องเป็นของเราเอง (ไม่ใช้ "Swing" ของ FACEIT / ชื่อของ Leetify)

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
  - `ct_has_kit` (bool, v2): CT ที่ยังรอดหลัง event อย่างน้อย 1 คนมีคีม (`has_defuser` ณ state tick)
  - `ct_defusing` / `ct_defusing_pre` (bool, v2): มี defuse ที่กำลังกู้และจะทันเวลา ณ หลัง event (tick) / ก่อน event (tick − 1) นิยามใน §2.2.2
- label: `t_won` ของรอบนั้น
- ตัดทิ้ง: warmup, post_match, รอบที่ไม่สมบูรณ์ (ไม่มี winner)

### 2.2 Training
- Logistic regression + L2 regularization (ค่าปรับประจำแมพจะหดเข้าหา 0 เองถ้าข้อมูลน้อย; แมพที่ < 5 แมตช์ตั้งเป็น 0)
- ห้าม pip install เพิ่ม: เช็คก่อนว่า env มี `scikit-learn` / `statsmodels` ไหม ถ้าไม่มีให้เขียน IRLS / gradient descent ด้วย numpy (ไม่กี่สิบบรรทัด)
- weight: ทุกแถวในรอบเดียวกันมี label เดียวกัน → ให้ weight = 1/จำนวนแถวของรอบ (ทุกรอบมีน้ำหนักเท่ากัน)
- บันทึก model เป็น JSON (coefficients + feature list + training manifest hash) ไม่ใช้ pickle: `impactagent/ratings/wp_model_v1.json` (เก็บไว้ ไม่เขียนทับ) และ **`wp_model_v2.json` = ตัวที่ระบบใช้** (`wp_model._MODEL_PATH`, default ของ `train-wp --out`)
- แบ่ง train/test ตาม **แมตช์** (ไม่ใช่ตามแถว)

### 2.2.1 ผล v1 (2026-11-05, `python -m impactagent train-wp data/parsed/wp_states.parquet`)
- ข้อมูล 30 แมตช์ · 639 รอบ · 4,962 แถว trainable · GroupKFold 5 fold ตามแมตช์ · weight = 1/แถว trainable ของรอบ · standardize feature (mean/std เก็บใน JSON, `predict_wp` ใช้ numpy อย่างเดียว) · C จาก {0.01, 0.1, 1, 10} ตาม log loss
- **feature ที่เลือก = ชุด D**: `t_alive, ct_alive, bomb_planted, time_left_pre, time_left_post, equip_diff_k, map_dust2, map_mirage, alive_prod, ct_can_defuse` (C = 1)
  - `ct_can_defuse` = หลัง plant และ C4 เหลือ ≥ 5s ถ้า CT ที่รอดมี kit ไม่งั้น ≥ 10s; v1 train ตอนที่ wp_states ยังไม่มีข้อมูล kit → ใช้ ≥ 10s ทุกแถว (v2 ใช้ kit + defuse ที่กำลังกู้ §2.2.2)
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
  - ข้อสังเกต: ภายในช่วงที่ CT ยังกู้ทัน (≥ 10s) `time_left_post` ยังบวกเล็กน้อย (30s 63.7% → 12s 59.0%) น่าจะเป็น selection (state ท้าย afterplant ที่ T ยังไม่ชนะมักเป็นตอน CT retake) แต่ขั้นที่ 10s ใหญ่กว่ามาก → โดยรวมเวลาน้อยไม่ทำให้ T แย่ลง; ช่วง 5–10s ที่ CT มี kit ถูกประเมินสูงไป (แก้ใน v2, §2.2.2)
- reliability (out-of-fold ชุด D, 10 ช่อง, pred / actual): 0.048/0.045 · 0.146/0.155 · 0.247/0.266 · 0.347/0.348 · 0.448/0.446 · 0.545/0.537 · 0.650/0.635 · 0.748/0.758 · 0.854/0.825 · 0.956/0.955 (ห่างไม่เกิน 0.03 ทุกช่อง)
- sanity (WP ของ T): 5v5 freeze end full buy (equip −2.5k) 44.9% · equip 0 49.8% · 5v4 90s 72.2% > 5v5 90s 46.9% ✓ · 4v4 40s ก่อน plant 45.7% → หลัง plant 67.6% ✓ · eco T (−15k) 23.3% · eco CT (+15k) 76.5% ✓
- **FACEIT round-start WP** (demo 1-8020514f แยก ไม่รวม train, `data/parsed/wp_states_faceit.parquet` สร้างจาก `--faceit-demo`): team_haineieie เป็น T 5 รอบ เฉลี่ย **62.3%** (FACEIT ≈ 61%) · เป็น CT 12 รอบ **54.4%** (FACEIT ≈ 55%) (ชุด A ได้ 64.9% / 52.3%)

### 2.2.2 v2: defuse kit + defuse ที่กำลังกู้ (2026-11-06) — ตัวที่ระบบใช้
- **ปัญหาใน v1:** `ct_can_defuse` ใช้ ≥ 10s ทุกแถว → ช่วง C4 เหลือ 5–10s ถือว่า CT กู้ไม่ทันแม้มีคีม (train 30 แมตช์: 36 รอบมี state ในช่วงนี้, CT ชนะ 16; ถ้า CT มีคีม ชนะ 12/17 · state ที่ model ทายช่วง 5–10s มีคีม CT ชนะ 38%, ไม่มีคีม 0%) และ model ไม่รู้ว่ามีคนกำลังกู้ → กู้เสร็จตอนเหลือ < 5s ทำให้ wp_pre ของ defuse สูงเกินจริง
- **`ct_can_defuse` (v2)** = หลัง plant และ (C4 เหลือ ≥ 5s ถ้า `ct_has_kit` ไม่งั้น ≥ 10s **หรือ** `ct_defusing`) · ไม่เพิ่ม feature ใหม่ (feature set D เดิม)
- **"กำลังกู้" ณ tick t** (`wp_states._defuse_intervals` + `is_defusing`) ต้องครบ 3 ข้อ:
  1. มี `bomb_begindefuse` ที่ tick b ≤ t ที่เริ่มตอน C4 เหลือ ≥ เวลากู้ของ **คนที่กด** (`haskit` ใน event: 5s / ไม่มี 10s)
  2. defuse นั้นยังไม่จบ: ยังไม่ถึง b + เวลากู้เต็ม (+2 tick, `DEFUSE_END_SLACK_TICKS`), ยังไม่ `bomb_defused`, คนกู้ยังไม่ตาย, คนเดิมยังไม่ `bomb_abortdefuse` / `bomb_begindefuse` ใหม่
  3. คนกู้คนนั้นยัง `is_defusing` = True ณ tick t (`ct_defusing`) หรือ t − 1 (`ct_defusing_pre`)
  - ไม่มี look-ahead: ทุกข้อใช้ event ที่เกิดแล้ว ณ tick นั้น (ข้อ 2 = "ยังไม่มี event ที่ทำให้จบ" ซึ่งรู้ได้ ณ t)
- **CS2 ไม่ยิง `bomb_abortdefuse`** (0 ครั้งในทุก demo ที่ตรวจ) การปล่อยมือเห็นได้จาก prop `is_defusing` ราย tick เท่านั้น (ข้อ 3) หรือเห็นเป็น `bomb_begindefuse` ซ้ำ · ถ้าไม่มีข้อ 3 จะ flag ผิดในเคสปล่อยมือไปยิง (เช่น ปล่อยตอนเหลือ 8s แล้วยิงคนตอนเหลือ 5.5s) ทำให้ CV ช่วง 5–10s แย่ลงเป็น 0.587
- **ไม่เพิ่ม state ที่ begindefuse / abort** (เลือกแบบแก้น้อยสุดแต่ถูก): ถ้าเพิ่ม state ต้องมี event_type / category ใหม่, แก้การแบ่งเครดิตและ invariant, และจำนวน state ของทุกแมตช์เปลี่ยน · แบบ flag ใช้ state เดิมทั้งหมด แค่เพิ่ม column ใน wp_states · ต้องมี `ct_defusing_pre` แยก เพราะ defuse มักเริ่มหลัง state ก่อนหน้า (wp_pre ของ e ใช้ flag ของแถว e เอง ไม่ใช่ของ state ก่อนหน้า, §3.1)
- ข้อมูลใหม่: `parse_ticks` ตัวเดิมของ `_read_timers_and_equip` เพิ่ม `has_defuser`, `is_defusing` ที่ state tick และ tick − 1 · `wp-states` 34 demo ใช้ ~7.5 นาที
- train: state ที่ train ได้ (trainable) ที่ `ct_defusing` = True มีแค่ 7 แถว และทุกแถวเวลาพออยู่แล้ว → model v2 เท่ากันทั้งแบบ kit อย่างเดียวและแบบ kit + กำลังกู้ (ผลของ "กำลังกู้" อยู่ที่ wp_pre ใน credit: `ct_defusing_pre` 146 แถว)

| | v1 | v2 (kit) | **v2 (kit + กำลังกู้)** |
|---|---|---|---|
| C | 1 | 10 | 10 |
| CV log loss / Brier ทั้งหมด | 0.4491 / 0.1471 | 0.4484 / 0.1469 | **0.4484 / 0.1469** |
| หลัง plant (773 แถว, OOF) log loss / Brier | 0.3418 / 0.1068 | 0.3358 / 0.1049 | **0.3358 / 0.1049** |
| หลัง plant ช่วง 5–10s (14 แถว) | 0.5565 / 0.1894 | 0.2727 / 0.0842 | **0.2727 / 0.0842** |
| reliability หลัง plant (C=1) 0.0–0.2 / 0.2–0.4 (pred/actual) | 0.098/0.049 · 0.303/0.203 | 0.095/0.018 · 0.303/0.230 | เท่า v2 (kit) |
| `ct_can_defuse` std / raw | −0.714 / −1.99 | −1.967 / −5.46 | **−1.967 / −5.46** |
| `bomb_planted` std / raw | 0.958 / 2.64 | 2.216 / 6.11 | **2.216 / 6.11** |
| sanity 2v2 planted 12s / 8s / 3s | 59.0 / 91.0 / 90.5% | 58.8 / 99.7 / 99.7% | 58.8 / 99.7 / 99.7% |
| sanity 8s CT มีคีม / 3s กำลังกู้ | – | – | **57.7% / 56.2%** |
| round-start FACEIT 8020514f T / CT (≈61 / ≈55) | 62.3 / 54.4% | 62.2 / 54.4% | 62.2 / 54.4% |
| FACEIT 8020514f Pearson All / T / CT | 0.907 / 0.925 / 0.915 | 0.909 / 0.924 / 0.915 | **0.909 / 0.924 / 0.915** |
| FACEIT 8020514f MAE All / T / CT | 2.32 / 3.11 / 2.37 | 2.32 / 3.08 / 2.41 | **2.32 / 3.08 / 2.41** |
| FACEIT 4cb4009a Pearson All / T / CT | 0.973 / 0.975 / 0.949 | 0.951 / 0.943 / 0.894 | **0.977 / 0.943 / 0.967** |
| FACEIT 4cb4009a MAE All / T / CT | 0.85 / 2.03 / 1.84 | 1.13 / 2.31 / 2.26 | **0.78 / 2.31 / 1.86** |
| 4cb4009a r2 wp_pre ก่อน defuse (กู้เสร็จตอนเหลือ 3.3s, เริ่มตอน 13.3s ไม่มีคีม) | 0.438 | 0.960 | **0.093** |
| ↳ เครดิต defuse ของคนกู้ / แถว time ฝั่ง CT ก่อน defuse | +0.438 / −0.333 | +0.960 / −0.858 | **+0.093 / +0.009** |
| validate-all · invariant (a)–(c) 5 แมตช์ | ผ่าน | ผ่าน | **ผ่าน** |

- Impact ต่อผู้เล่นเปลี่ยนจาก v1 สูงสุด (pp/รอบ): inferno 0.06 · mirage 0.05 · dust2 0.04 · FACEIT 8020514f 0.23 · 4cb4009a 1.07
- set E (= D + `ct_has_kit` เป็น feature, เทียบใน CV เท่านั้น): log loss 0.4475 ดีกว่า D 0.0009 (< std ระหว่าง fold ~0.01) และช่วง 5–10s แย่กว่าเล็กน้อย → ยังใช้ D
- ผลกระทบตอนวัดก่อนแก้: train 30 แมตช์ state ที่ WP เปลี่ยนเพราะคีม 18/6,272 (17 รอบ, Σ|ΔWP| เปลี่ยน 1.26%); validation 3 pair ของ Leetify ไม่มี state ที่ CT รอดในช่วง 5–10s

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
- `wp_pre(e)` = WP ของ state ก่อนหน้า แต่เลื่อนนาฬิกาไปที่ tick ของ e (`time_left_s` ก่อนหน้า − Δtick/tickrate; `ct_can_defuse` คิดใหม่จากเวลา) · `equip_diff_k` และ `ct_has_kit` ใช้ของ state ก่อนหน้า (คนถือคีมอาจตายใน e) · `ct_defusing` ใช้ `ct_defusing_pre` ของแถว e เอง (defuse ที่เริ่มหลัง state ก่อนหน้า, §2.2.2) · state ก่อนหน้าที่ตัดสินแล้วใช้ rule-fixed
- `delta_time = wp_pre(e) − wp_after(e ก่อนหน้า)` → แถว part/category `time`: default `time_credit: survivors` = คนที่รอดก่อน e ของแต่ละฝั่งแบ่งเท่ากัน (T +Dt / CT −Dt; ไม่มีคนรอด → ทั้งทีม) · `none` = steam_id null ไม่ให้ใคร (§3.7)
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
- state ตอนเริ่มกู้ (เครดิตของการเริ่มกู้ไปอยู่ในแถว `time`, §3.8)

### 3.4 Output
- `rating_events` (data-model §2.4) → `data/parsed/<demo>/rating_events.parquet`: 1 แถวต่อ (state, part, ผู้รับ) คอลัมน์ `match_id, round_no, seq, sub, tick, event_type, event_ref, part, steam_id (nullable), is_bot, side, category, delta, wp_pre, wp_after`
- `player_round_ratings.parquet` (match_id, round_no, steam_id, side, rating = Σ delta ของผู้เล่นในรอบ รวมส่วน time ของ survivors, ไม่รวม disconnect) = ค่าของ `player_rounds.rating` (ยังไม่ merge เข้า `build_player_rounds`)
- metric `impact` / `impact_ct` / `impact_t` ใน registry: `aggregation: mean` ต่อรอบที่เล่น, scopes `[all, CT, T]`, `status: custom`, unit `pp` (×100 แล้ว); ข้ามแมตช์ใช้ Σ rating / Σ รอบ · join ใน `compute_match_metrics` (truth ไม่มี key `impact` → ไม่ gate)
- invariant (`check_invariants`, CLI exit 1 ถ้า fail) ต่อรอบ ±1e-9: (ก) Σ แถวฝั่ง T (รวม time/disconnect) = t_won − wp_start (ข) Σ T + Σ CT = 0 (ค) Σ ผู้เล่น/bot ฝั่ง T + Σ time/disconnect ฝั่ง T = (ก) และไม่มีแถว steam_id null นอก time/disconnect/bot · ต่อ state: Σ แถว T = wp_after − wp_pre

### 3.5 ผล v1 (2026-11-05)
- invariant ผ่านทุกรอบ: FACEIT 8020514f 17/17, inferno 13/13, mirage 24/24, dust2-85507dfb 20/20
- เทียบ FACEIT Swing (dust2-8020514f, 10 คน, % ต่อรอบ): Pearson All +0.88 / T +0.92 / CT +0.89 · Spearman All +0.78 / T +0.86 / CT +0.94 · MAE 2.5 / 3.0 / 3.1 pp · ผลรวมทีมชนะ ฝั่ง T ours +38.6 vs FACEIT +39.2, ฝั่ง CT +7.0 vs +11.4 · ลำดับในทีมชนะ ρ 0.90 (สลับแค่ ch4dum/o2donggg), ทีมแพ้ ρ 0.30
- ส่วนที่ไม่มีใครได้ (time) = −4.0 pp ต่อรอบสำหรับ T (เวลาเดินทำให้ T เสีย) ทำให้ผลรวมทีมเราน้อยกว่า FACEIT (ทีมชนะ All +16.3 vs +19.6)

### 3.6 ทดลอง §6.6 (2026-11-05)
- config ใหม่ `time_credit: none | survivors` (default `none`; CLI `--time-credit`): `survivors` = delta_time ของแต่ละ state แบ่งเท่ากันให้คนที่ยังรอดก่อน event ของแต่ละฝั่ง (T +Dt, CT −Dt; ไม่มีคนรอด → ทั้งทีม) category `time` · invariant ผ่านทั้ง 2 โหมดใน 4 แมตช์
- FACEIT 8020514f (10 คน, pp ต่อรอบ):

| | none | survivors |
|---|---|---|
| Pearson All / T / CT | 0.883 / 0.921 / 0.888 | **0.907 / 0.925 / 0.915** |
| Spearman All / T / CT | 0.782 / 0.855 / 0.939 | 0.830 / 0.855 / 0.952 |
| MAE All / T / CT | 2.50 / 3.00 / 3.10 | **2.32** / 3.11 / **2.37** |
| ทีมชนะ All (FACEIT +19.57) | +16.28 | **+19.76** |
| ทีมชนะ ฝั่ง T (+39.15) / ฝั่ง CT (+11.43) | +38.57 / +6.99 | +37.69 / **+12.29** |
| ลำดับในทีม ชนะ / แพ้ (ρ) | 0.90 / 0.30 | 0.90 / 0.30 |

  ⇒ FACEIT น่าจะให้ส่วนเวลากับคนรอด (ผลรวมทีมตรงขึ้นมาก) แต่แค่ 1 แมตช์
- 3 คนที่ |diff| มากสุด (survivors): o2donggg +4.0 (ของเราสูงกว่า), FigaDiGuine −3.6, whyskushy +3.5 (ch4dum −3.4 ตามมา)
  - o2donggg (20-7, ADR 131): damage part +7.8 pp สูงสุด และ death เสียเฉลี่ยน้อย (−16 ต่อครั้ง) → เราน่าจะให้ damage share มากกว่า FACEIT
  - whyskushy (7-14, ADR 57): damage_assist +1.95 และ afterplant +2.0 ดันขึ้น ทั้งที่ ADR ต่ำ → เหมือนกัน: damage share ของเราใจดีกับคนที่ทำ damage แล้วเพื่อนเก็บ kill
  - FigaDiGuine (9-15) / ch4dum (23-9): death แพง (−19 / −23 ต่อครั้ง เพราะตายตอน WP ทีมสูง) → FACEIT น่าจะหักต่อ death น้อยกว่า หรือแบ่งความผิดของ death ให้คนอื่น
  - ข้อสรุปเบื้องต้น: ส่วนต่างหลักอยู่ที่ damage share (0.30) กับราคาของ death ไม่ใช่หมวด situational — ยังไม่ปรับ (1 แมตช์)
- **Leetify:** truth JSON 3 pair มี `leetify_rating` (ต่อผู้เล่น, ทั้งแมตช์, หน่วยเดียวกับเรา = pp ต่อรอบ), `hltv_rating`, `personal_performance` และ `utility_*_rating`; **ไม่มี rating breakdown ต่อหมวด**
  - impact ของเรา vs `leetify_rating` (10 คน/แมตช์), none → survivors: inferno r 0.992 → 0.991 (MAE 0.92 → 1.22) · mirage r 0.889 → 0.910 (ρ 0.37 → 0.39, MAE 1.45 → 1.31) · dust2 r 0.975 → 0.980 (MAE 1.56 → 1.51)
  - mirage ρ ต่ำ เพราะคนที่ค่าใกล้ 0 สลับลำดับกัน (Boonrywaa ของเรา +4.6 vs Leetify +0.9; J −0.6 vs +1.7)
  - ค่า Leetify เป็น calibration data เก็บใน gitignored `data/validation/` เท่านั้น

- **FACEIT แมตช์ที่ 2** (mirage-4cb4009a, อยู่ในชุด train ของ WP → ดูดีเกินจริงได้): invariant ผ่านทั้ง 2 โหมด
  - none: Pearson All 0.981 / T 0.972 / CT 0.967, MAE 0.74 / 2.41 / 2.10 · survivors: 0.973 / 0.975 / 0.949, MAE 0.85 / 2.03 / 1.84 · ลำดับในทีม ρ 0.90 / 1.00 ทั้ง 2 โหมด
  - **รวม 2 แมตช์ (20 คน)** none → survivors: Pearson All 0.916 → 0.929, T 0.921 → 0.920, CT 0.905 → 0.916 · MAE All 1.62 → 1.58, T 2.71 → 2.57, CT 2.60 → 2.11 ⇒ survivors ดีกว่าเล็กน้อยโดยรวม ยังไม่ชัดพอจะเปลี่ยน default
  - ผลรวมทีมแยกฝั่งต่าง FACEIT มาก: team 1 ฝั่ง T ours +8.4 (none) vs FACEIT −3.1, ฝั่ง CT +2.3 vs +13.6 → WP เริ่มรอบของ FACEIT บน mirage ให้ T สูงกว่าเรา ~11 pp ต่อรอบ (ของเรา map_mirage เป็นลบ) ทั้งที่ All ตรง (+5.3 vs +5.3)

### 3.7 Decision: `time_credit = survivors` (owner, 2026-11-05)
- default ใน `credit.yaml` = `survivors` (`--time-credit none` ยังใช้ได้)
- เหตุผล: รวม 2 แมตช์ FACEIT (20 คน) Pearson All 0.929 vs 0.916, MAE 1.58 vs 1.62 และผลรวมทีมใกล้ FACEIT กว่า (dust2 ทีมชนะ +19.76 vs FACEIT +19.57; none +16.28) · Leetify สองโหมดสูสี (r 0.99 / 0.89–0.91 / 0.98)
- invariant ผ่านทุกแมตช์ (FACEIT 2 + validation 3) ด้วย default ใหม่

### 3.8 Known issues (ค้าง)
- **WP mirage ต่างจาก FACEIT ~11 pp ต่อรอบฝั่ง T** (mirage-4cb4009a: ผลรวมทีม 1 ฝั่ง T ours +6.0 vs FACEIT −3.1, ฝั่ง CT +3.7 vs +13.6, ทั้งที่ All ตรง) → WP เริ่มรอบของเราให้ T บน mirage ต่ำกว่า FACEIT · รอ demo mirage เพิ่ม (ตอนนี้ 6 แมตช์ train)
- **เครดิตตอนเริ่มกู้** (v2, §2.2.2): ไม่มี state ที่ begindefuse → WP ที่ลดลงตอนเริ่มกู้ไปอยู่ในแถว `time` ของ event ถัดไป แบ่งให้ CT ที่รอดทุกคน (`time_credit: survivors`) ไม่ใช่คนกู้คนเดียว · แก้ได้ด้วย state `begin_defuse` ถ้าต้องการ
- **4cb4009a ฝั่ง T Pearson 0.975 → 0.943** ตั้งแต่ใส่ kit (v1 → v2) ทั้งที่ CT / All ดีขึ้น · แมตช์นี้อยู่ใน train · ดูอีกครั้งเมื่อมีแมตช์ FACEIT ที่ 3
- **`ct_has_kit` เป็น feature (set E)** ดีกว่า D ไม่เกิน noise ที่ 30 แมตช์ → ลองใหม่ตอนมี 100 แมตช์
- damage share 0.30 / ราคา death ยังไม่ปรับ (ส่วนต่างหลักกับ FACEIT, §3.6) รอข้อมูลเพิ่ม

## 4. RWS
- รอบที่ทีมชนะ: 100 แต้มแบ่งตามสัดส่วน damage ใส่ศัตรูในรอบนั้น (ไม่นับ team damage)
- **damage = sequential** ไม่ใช่ `dmg_effective`: แต่ละ hit cap ที่ HP ที่เหลือก่อนโดน (`min(dmg_raw, HP_remaining)`) เรียงตามลำดับ event ต่อ (รอบ, เหยื่อ) ส่วน `dmg_effective` รวม hit ใน tick ที่เหยื่อตายเป็นกลุ่มเดียว ("killing tick = hits รวมกัน = HP ก่อน tick") ซึ่งทำให้ RWS ต่างจาก FACEIT ใน kill tick ที่มีหลาย hit พร้อมกัน (shotgun / หลายคนยิงตายใน tick เดียว)
- team damage ไม่นับเป็นแต้ม แต่ยังลด HP ของเหยื่อในลำดับ sequential (enemy hit ที่ตามหลัง team hit จึงถูก cap ต่ำลง)
- ชนะด้วยระเบิดระเบิด → planter ได้ 30, อีก 70 แบ่งตาม damage · ชนะด้วยการกู้ → defuser ได้ 30, 70 ตาม damage
- รอบที่แพ้ = 0 · ค่าแมตช์ = เฉลี่ยต่อรอบที่เล่น · scopes `[all, CT, T]`
- edge case: ทีมชนะที่ทำ damage รวม 0 (ชนะหมดเวลา/ศัตรู save) → แบ่งเท่ากันในคนที่เล่นรอบนั้น (match นี้เจอ 0 รอบ)
- variant ที่ทดสอบ (2b, mean / max abs err เทียบ FACEIT 30 ช่อง): base `dmg_effective` 0.019/0.094 · ตัด damage หลังรอบจบ 0.029/0.094 (แย่ลง) · cap (attacker,victim,round)=100 0.019/0.094 (ไม่เปลี่ยน) · **sequential 0.002/0.005 ✓ (ตรง 30/30 ±0.01)**
- **แมตช์ที่ 2** (mirage-4cb4009a, 2026-11-05; อยู่ในชุด train ของ WP): ชื่อในเกมต่างจาก FACEIT 2 คน (`krvmz` ↔ krvmzy, `Riend-` ↔ RESURECTON-; validate-faceit ยังไม่มี alias) · ถ้า map ชื่อแล้ว **off 10/30**: ฝั่ง T ตรงทุกคน (±0.004) แต่ CT ของ team b (รอบ 13–24) ผิด JungYoon −0.157, krvmzy +0.066, teng +0.038, pure666 +0.027, RESURECTON- +0.022 (ผลรวมทีม ≈ 0 → แบ่ง 100 แต้มต่างกัน ไม่ใช่จำนวนรอบ) · สมมติฐานที่ลองแล้ว ไม่ดีขึ้น: ตัด damage หลัง round end (16/30), ตัดก่อน freeze end (10/30), cap ด้วย `victim_hp_after` ของเกม (19/30), team hit ไม่ลด HP (15/30) → ยังไม่รู้สาเหตุ, rws คง `calibrating`
- รอบ CT ของ team b (mirage): t_killed 15, 16, 19, 21, 23, 24 · ct_killed 14, 17 · bomb_exploded 13, 18 · bomb_defused 20 · **time_ran_out 22** · disconnect: -pure666 รอบ 2 และ 24 (dust2 ไม่มีทั้งหมดเวลาและ disconnect) · ส่วนต่างของ JungYoon รวมแค่ ~1.9 แต้มใน 12 รอบ (≈ damage 10 HP ในรอบเดียว)
- กฎที่ทดลอง (scratch, off/30 dust2 · mirage; ต้อง dust2 30/30 ด้วย):

| กฎ | dust2 | mirage |
|---|---|---|
| base (rws.py ปัจจุบัน) | 0 | 10 (max 0.157) |
| (ก) หมดเวลา: 100 แบ่งเท่าคนรอดฝั่งชนะ | 0 | 10 (max 8.36) |
| (ก') หมดเวลา: แบ่งตาม damage เฉพาะคนรอด | 0 | 10 (max 8.36) |
| (ข) หมดเวลา: ตาม damage, รวม 0 → แบ่งเท่า | = base (rws.py ทำอยู่แล้ว; รอบ 22 มี damage) | = base |
| (ค) defuse ไม่มีโบนัส 30 (เช็คว่าโบนัสใช้อยู่) | 10 | 18 → **โบนัส 30 + 70 ถูกแล้ว** |
| (ง) damage ใส่คนที่ disconnect ไม่นับ | 0 | 10 (ไม่เปลี่ยน) |
| (ง') + คน disconnect ไม่ได้ส่วนแบ่ง | 0 | 10 (max 4.76) |
| (จ) damage ตัวเอง/world (C4 100, molotov 24) ไม่ลด HP | 0 | **8** (max 0.213) |
| (ฉ) เฉพาะ enemy hit ลด HP | 0 | 14 |
| (ช) ไม่ cap (dmg_raw) | 25 | 30 |

  ⇒ ไม่มีกฎที่ได้ 30/30 ทั้ง 2 แมตช์ ไม่แก้ rws.py · (จ) ดีขึ้นนิดแต่ max แย่ลง ต้องมีแมตช์ที่ 3 หรือ per-round truth
- `status: exact` เมื่อตรง FACEIT ครบ 10 คน × 3 scope ทุกแมตช์ · **ตอนนี้ `calibrating`:** dust2-8020514f 30/30 แต่ mirage-4cb4009a ต่างจาก FACEIT ≤ 0.16 (10/30 ช่อง) ยังหากฎไม่เจอ รอแมตช์ FACEIT ที่ 3

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
6. เทียบกับ FACEIT Swing / Leetify, ปรับ config, อัปเดต roadmap ✅ (2026-11-05, §3.6–3.7) → **Phase 2 ปิด**
7. WP v2: `ct_has_kit` + defuse ที่กำลังกู้ใน wp_states → `wp_model_v2.json` ✅ (2026-11-06, §2.2.2)
