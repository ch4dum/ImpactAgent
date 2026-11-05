# Roadmap

สถานะงานและแผนของ ImpactAgent อัปเดตไฟล์นี้ทุกครั้งที่จบงานหนึ่งชิ้นหรือมีการตัดสินใจใหม่

**MVP:** อัป `.dem` ฟรี → ได้หน้าสถิติแมตช์ → คุยกับ AI coach (Leetify เก็บเงินทั้งการอัปโหลดและ Ask AI)

---

## ✅ เสร็จแล้ว
- **Phase 0 Research:** metric spec, parameter reference, Leetify sitemap (`docs/metrics/`, `docs/research/`)
- **Data model v0.1** (`docs/design/data-model.md`)
- **Parser + CLI:** `.dem` / `.dem.bz2` / `.dem.gz` (`.dem.zst` ถ้ามี zstandard), `inspect` · `parse` · `validate` · `validate-all`, guard กันจับคู่ demo ผิดแมตช์
- **Parse safety:** จำกัดขนาด .dem หลังแตก ≤ 1 GiB (หยุดแตกทันที ลบ temp) + timeout 300s (parse ใน child process ที่ถูก kill เมื่อเกินเวลา)
- **General + Utility ตรงกับ Leetify:** Inferno 245/245, Mirage 290/290 (holdout ได้ 274/290 ก่อนแก้โค้ด) สถานะของแต่ละกฎอยู่ใน spec §8
- **Trades (succeeded) + opening traded % + opening duels + clutches:** core รวม Inferno 275/275, Mirage 320/320; opening 37/37 รอบ; clutch 43/43 (รวมเคสออกเกม, spec §8)

## ✅ Phase 1: Metrics engine (ครบหนึ่งแมตช์) — ปิดแล้ว (2026-11-05)
- [x] Trades: `trade_windows`, succeeded, opening traded %, clutches
- [x] Metric registry (`impactagent/metrics/registry.yaml`): 54 metric (42 exact, 12 calibrating); `validate-all` เช็คว่า registry ครบ/ถูก format และ calibrating ไม่ gate
- [x] Head Accuracy: นับต่อนัด ไม่นับ AWP / ลูกซอง; นัดที่ทะลุหัวไปโดนคนที่ 2 ไม่นับเป็นหัว (inferno 10/10, mirage 10/10)
- [x] `shots` features + `engagements` (`impactagent/parse/aim.py`) + Aim metrics (`impactagent/metrics/aim.py`); core รวม **inferno 305/305, mirage 350/350**
  - exact: `shots_fired` (ไม่นับลูกซอง และนัดใน tick ที่คนยิงตาย; Mirage holdout เจอทั้งสองกฎ), `accuracy_all`, `accuracy_head`
  - calibrating (ตรงราย player inferno / mirage): spotted acc 3/10, 6/10 · counter-strafe 2/9, 3/9 · spray 0/7, 3/8 · first bullet 1/10, 0/10 · TTK 1/10, 0/10 · TTD 0/10, 0/10 · crosshair 0/10, 0/10
  - Holdout Mirage ก่อนแก้โค้ด: core aim 9/20 (shots_fired 3/10, accuracy_all 6/10), calibrating 15/77
- [x] Validation pair 3 `dust2-85507dfb` (holdout ตัวจริง, 2026-11-05): ก่อนแก้โค้ด core 353/360, opening 20/20, clutch 25/25; head accuracy นับ SSG08 (ch4dum 0.62); ชื่อ non-ASCII จับคู่ครบ.
- [x] Dust2 core (2026-11-05): shots_fired นับ taser; flash assist ให้เครดิตทุก flash ที่เหยื่อยังบอด; molotov damage นับเฉพาะไฟ → core 356/360 (Inferno 305/305, Mirage 350/350 ไม่พัง)
- [x] **Known exceptions** (`impactagent/validate/known_exceptions.yaml`, 2026-11-05): ช่อง (pair, player, metric) ที่ยังไม่รู้สาเหตุ แสดงเป็น `known` ไม่ gate, ไม่ใช่ tolerance; เตือน STALE ถ้ากลับมาตรง. ตอนนี้ 4 ช่องของ Dust2 → `validate-all` ผ่านทั้ง 3 pair (Dust2 core 356/356 +4 known)
- [x] Visibility จุดเป้า 8 จุด เป็นค่าหลัก (`TARGET_LAYOUT`, 2026-11-05): capsule 24 จุดไม่ดีกว่าชัดเจน; crosshair แบบมุมไปหาหัวตอน first seen ไม่ใกล้กว่า → คงนิยามเดิม; นิยามของเราสำหรับ metric calibrating อยู่ใน spec §1 / §3
- [x] **Visibility module** (`impactagent/visibility/`, 2026-11-05): interface เดียว backend `spotted` (ของเกม) / `raycast` (awpy mesh) + lag window 7 tick + ควันทรงกลม + FOV 50°; `python -m impactagent visibility DEMO...` รายงานผล
  - kill ปกติที่ "เห็น" (raycast เต็ม): inferno 72/72, mirage 150/152; ผ่านควัน: 0/7, 2/7; `spotted` ของเกมเห็นแค่ ~75% ของ kill ปกติ
  - ความเร็ว: raycast ~29k คู่-tick/วินาที
- [x] Visibility v1 (raycast กับ map geometry)
  - [x] Spike awpy 3.1.1 `VisibilityChecker` (`scripts/visibility_spike.py`)
  - [x] Lag compensation window 7 tick ย้อนเห็นครบ normal kills 100%
- [x] **Round buy type + Map Zones** (2026-11-05):
  - Buy types: `pistol` (รอบแรกของแต่ละครึ่ง/OT), `eco` (< $1,500), `semi-eco` ($1,500–2,499), `force` ($2,500–3,899), `full` (≥ $3,900) คำนวณจากมูลค่าอุปกรณ์เฉลี่ยของทีมตอน freeze end บันทึกลง `rounds`
  - Map Zones: เพิ่ม `attacker_place`, `victim_place` ใน `damages` (และ `kills` ที่มีอยู่เดิม) พร้อมสร้างตารางสรุป `player_zones` (kills/deaths ต่อโซน แยก T/CT)
  - เพิ่ม metric `equip_value_avg` ลง registry (calibrating, นิยามของเรา) และ `validate-all` ผ่านครบทุก pair (exit 0)

---

## 📌 นิยามของเรา / Known Exceptions (ข้อที่ค้างและสมมติฐาน)
- **Trade opportunities / attempts:** ลองใหม่ด้วย visibility แล้ว raycast ได้ 23/40 บน Inferno แต่ holdout Mirage แค่ 11/40 (นิยามเดิม 22/40, 25/40) → คงนิยามเดิม, calibrating; ต้องมี truth ราย death เพื่อ calibrate ต่อ (spec §3)
- **Dust2 4 ช่อง known exceptions (spec §8):**
  - unused utility 3 คน (Chainnizy -$200, gxmxi -$200, โจ๊กเก๊า -$300 ขาดไปคนละลูก Flash/Flash/Smoke): ตรวจ inventory timing (-64..0 tick), active weapon, เก็บของตกพื้น, C4/world death แล้วไม่พบสาเหตุที่เข้ากับทั้ง 3 คน
  - blind duration yyh (3.15 vs 3.00): ตัดลูก r16 (yyh ปาแล้วตายก่อนระเบิดลง) จะได้ 3.00 พอดี แต่ขัดแย้งกับ Mirage ch4dum r21 ที่ Leetify นับปกติ
- **Aim calibrating metrics (spec §1 / §3):**
  - TTD bias: 8 target points ลด bias เหลือ -125 / -83 / -105 ms (24 จุด capsule กิน ray x7 ไม่ช่วยลด bias ชัดเจน)
  - Crosshair placement: นิยาม 3D head-angle ไม่ใกล้ขึ้น คงนิยามเดิม
  - Spray accuracy: Leetify ไม่ได้คิดแบบ hit/shot ธรรมดา (yyh 0.83 ทั้งที่ accuracy 0.11) คงสถานะ calibrating
- **Hypotheses ใน spec §8 (🟡):** รอ demo แมตช์ใหม่ที่แยกเคสได้ เช่น kill ระหว่างบอด ≤ 1.1s, capped molotov / team-HE hits

---

## ⏳ Phase 2: Ratings (สูตรของเราเอง ไม่ใช้ชื่อ Leetify)
- [x] **`wp_states` builder + CLI `wp-states`** (impact-spec §6.3, ยังไม่ train, 2026-11-05): 1 แถว/state (freeze end, kill, plant, defuse, explode, round end) · features `t_alive`/`ct_alive`, `bomb_planted`, `time_left_s`, `equip_diff_k`, `map`, label `t_won` · column `trainable` แยกแถวที่ model ต้องทาย vs rule-fixed · ตัด validation match ด้วย fingerprint (map + จำนวนรอบ + สกอร์ + ชุด steam_id) · สร้าง `data/train_demos/manifest.csv` อัตโนมัติ ผล: 30/34 แมตช์ (ตัด 4 validation, 0 parse fail), 713 รอบ, 6,285 state (4,972 trainable); แมตช์/แมพ dust2 15 · mirage 6 · cache 4 · ancient 3 · inferno 2
- [x] **WP model v1 + CLI `train-wp`** (impact-spec §6.4 / §2.2.1, 2026-11-05): logistic L2 บน feature ที่ standardize (mean/std ใน `wp_model_v1.json`, predict numpy-only, sklearn เฉพาะ `train_wp.py` / extra `[train]`) · GroupKFold 5 ตามแมตช์ · ชุด D (A + map + alive_prod + ct_can_defuse) C=1: Brier 0.1472 log loss 0.4491 vs baseline 0.1638 / 0.4955 · reliability ห่าง ≤ 0.03 ทุกช่อง · FACEIT round-start WP T 62.3% (≈61) CT 54.4% (≈55)
- [x] **Impact credit + `rating_events` + metric `impact` + CLI `impact`** (impact-spec §3 / §6.5, 2026-11-05): แยก ΔWP จากเวลา (แถว `time` ไม่ให้ใคร) · kill แบ่ง 0.35/0.30/0.15/0.20 (`credit.yaml`, damage แบบ sequential จาก rws) · disconnect ไม่ให้ใคร · 9 หมวด + time + disconnect · invariant ผ่าน 4 แมตช์ (FACEIT, inferno, mirage, dust2) · เทียบ FACEIT Swing: Pearson All 0.88 / T 0.92 / CT 0.89, MAE 2.5 pp
- [ ] Impact: เทียบ Leetify rating-breakdown, ปรับ config (impact-spec §6.6)
- [ ] Aim / Utility / Positioning Score: แยกตามกลุ่มปืน (sniper / rifle / pistol) ไม่ให้ metric ที่เป็น n/a ดันคะแนน และบอกความมั่นใจตามขนาดตัวอย่าง (บทเรียนจาก Aim 100 ของ Leetify ในแมตช์ที่ใช้ AWP)

## ⏳ Phase 3: Backend
- [ ] Supabase: Postgres (ตาราง core) + Auth (Steam OpenID ผ่าน backend เรา)
- [ ] เก็บ event ละเอียดเป็น Parquet; ไฟล์ `.dem` ลบทิ้งหลัง parse
- [ ] Upload: presigned URL รับ `.dem.bz2` → queue → worker (parse + metrics)
- [ ] FastAPI
- [ ] เก็บตำแหน่งผู้เล่นรายรอบไว้เผื่อ 2D Replay (ลดเหลือ 4–8 Hz: X/Y/Z, yaw, HP, อาวุธ, alive + เส้นทางระเบิด) บีบอัดแยกรายรอบ จะได้ไม่ต้อง parse demo ใหม่ตอนทำ replay

## ⏳ Phase 4: AI Coach
- [ ] LLM layer แบบเปลี่ยน provider ได้ (เริ่มที่ Gemini free tier)
- [ ] **Export สำหรับ AI ของ user เอง:** ไฟล์ JSON/Markdown สรุปแมตช์ + prompt ให้ import ไปใช้กับ ChatGPT / Claude / Gemini (ไม่มีต้นทุน)
- [ ] Tools: query `metric_values` / `engagements` + NL2SQL read-only
- [ ] Match report แบบเล่าเรื่อง (เกินกว่า "Your Match" ของ Leetify)
- [ ] Eval set: ชุดคำถามวัดคุณภาพคำตอบ

## ⏳ Phase 5: Frontend
- [ ] ตัดสินใจ stack + mockup
- [ ] Match page, Your Match + แชท AI, หน้าอัปโหลด, profile

## ⏳ Phase 6: Deploy & Architecture
- [ ] **Frontend:** Deploy บน **Vercel**
- [ ] **Storage:** อัปโหลด `.dem.bz2` ตรงไปยัง Cloudflare **R2** ด้วย Presigned URL
- [ ] **Database & Queue:** ตาราง `jobs` บน **Supabase** (สถานะคิว, retry, progress)
- [ ] **Worker (ระยะเริ่มต้น):** เครื่อง Laptop ทำหน้าที่เป็น **pull-worker**
  - รันใน Docker container (`restart: always`)
  - จำกัด resource (RAM / CPU) ไม่ให้กระทบการทำงานทั่วไป
  - ใช้ API key สิทธิ์จำกัด (Service Role / scoped key)
  - มีระบบ heartbeat รายงานสถานะเครื่องว่าพร้อมรับงาน
  - ทำ preload / cache สำหรับ awpy mesh ไว้ในเครื่อง
- [ ] **Worker Scaling (ระยะเติบโต):** ย้าย worker ไปยัง Cloud **VPS (RAM ≥ 4GB)** เมื่อมีปริมาณผู้ใช้งานเพิ่มขึ้น
- [ ] **Domain:** Subdomain บน `tammapol.com` (Cloudflare) เช่น `impactagent.tammapol.com` จนกว่าจะได้ชื่อ product
- [ ] **Security & Policy:** Rate limit / คุมค่า LLM, Terms of Service / Privacy Policy

## หลัง MVP
- [ ] **2D Replay** (งานแรกหลัง MVP หรือรวมใน Phase 5): radar + จุดผู้เล่น/ทิศที่มอง/kill feed/timeline รายรอบ (MVP ~1–2 สัปดาห์) → ระเบิดครบ, HP, แมพหลายชั้น (Nuke) · AI coach ลิงก์ไปที่ tick ใน replay ได้ · ภาพ radar เป็นของ Valve ต้องเช็คสิทธิ์ก่อนเปิดสาธารณะ
ดึงแมตช์อัตโนมัติด้วย share code · benchmark ตาม rank · Focus Areas · Highlights

---

## การตัดสินใจ
| เรื่อง | สถานะ |
|---|---|
| Database | **Supabase** (Postgres + Auth) |
| Domain | **tammapol.com** (Cloudflare) ใช้ subdomain ไปก่อน |
| Branches | `main` = rebuild (เดิมชื่อ `v2`, default บน GitHub) · `v1-draft` = prototype เดิม (เดิมชื่อ `main`) ไว้อ้างอิงเท่านั้น (2026-11-05) |
| ชื่อ product | ยังไม่ตัดสินใจ (ห้ามมี CS2 / Counter-Strike) |
| LLM | Gemini API free tier + export ให้ user ใช้ AI ของตัวเอง |
| Buy type thresholds | **นิยามของเราเอง** (2026-11-05): pistol = รอบแรกของแต่ละครึ่ง/OT, eco < $1,500, semi-eco $1,500–2,499, force $2,500–3,899, full ≥ $3,900 |
| Map Zones | **last_place_name** เก็บใน kills, damages และสรุปเป็น table `player_zones` (kills/deaths ต่อโซน แยก T/CT) (2026-11-05) |
| Visibility | **raycast เป็นค่าหลัก** `spotted` ยังสลับใช้ได้ (`spotted` เห็น kill ปกติแค่ ~75%) (2026-11-05) |
| Lag compensation | **window คงที่ 7 tick** (เป้าหมายตำแหน่งใดก็ได้ใน 7 tick ล่าสุด) ไม่ย้อนตาม ping: tick ที่ต้องย้อนไม่สัมพันธ์กับ ping ของคนยิง (rank corr 0.01, 64 hit, ping 13–57ms) (2026-11-05) |
| Aim shot set | นัดที่นับใน accuracy ทุกตัว = ปืน + **taser** (ไม่นับมีด / ระเบิด / **ลูกซอง**) ทั้งช่วงรอบรวมหลัง round_end ยกเว้นนัดใน tick ที่คนยิงตาย; hit = ทำ damage ศัตรูใน tick เดียวกัน (2026-11-05) |
| Engagement v1 | สร้างจาก damage: สแกนย้อนทีละ tick ขณะ A เห็น B (gap ≤ 8 tick, ≤ 2.5s) ยังไม่มี engagement ที่ไม่มี damage (2026-11-05) |
| Target points | 8 จุด (หัว คอ อก เอว เข่า เท้า + ไหล่ ±14u) `TARGET_LAYOUT = "8"`; 24 จุดไม่คุ้ม (2026-11-05) |
| Calibrating metrics | ใช้นิยามของเราเอง (spec §1 / §3 "นิยามของเรา") จนกว่าจะทำซ้ำนิยาม Leetify ได้ (2026-11-05) |
| Smoke | ทรงกลม R 144, ศูนย์กลาง +32 จากจุดระเบิด, บล็อกตั้งแต่ระเบิด +0.5s ถึง `smokegrenade_expired`; calibrate บน inferno (2026-11-05) |
| Trade window | 4.0s (ช่วงที่ข้อมูลยอมรับ [3.48, 4.47) s) |
| Known exceptions | เฉพาะช่องที่ระบุ (pair, player, metric, reason) เมื่อหาสาเหตุไม่เจอ; ลบเมื่อแก้ได้ (2026-11-05) |
| validate gating | gate core metric + opening duels + clutches; metric ที่ registry ตั้ง `status: calibrating` (ตอนนี้ trade opp/att) รายงานแต่ไม่ fail |
| Map geometry | awpy-data `.mesh` (`pip install -e .[visibility]`, cache `~/.awpy/<ClientVersion>`, ไม่ commit) เลือก release ตาม `csgo_v<build>` ใน header ของ demo (2026-11-05) |
| Parse limits | .dem หลังแตก ≤ 1 GiB (`MAX_DEMO_BYTES`), parse ≤ 300s (`PARSE_TIMEOUT_SECONDS`); เวลาแตกไฟล์ไม่นับใน timeout (คุมด้วยขนาดแทน) |
| WP state timers | `mp_roundtime` อ่านจาก `server_cvar` (นาที → วินาที); `mp_c4timer` ไม่มีใน demo → ใช้ `C4_TIMER_S`=40; เตือนถ้าค่าจาก demo ต่าง constant >1s (2026-11-05) |
| WP equip_diff_k | (Σ `current_equip_value` T − CT ของผู้เล่นที่ยังรอด)/1000 ณ state tick นับ "รอด" จาก kills; อ่าน tick data เฉพาะ tick ที่เป็น state ไม่เก็บทั้งเกม (2026-11-05) |
| `parse_demo(fast=)` | `fast=True` ข้าม trade_windows + aim/visibility (ตาราง event เหมือนเดิมทุกกรณี); default `False` (2026-11-05) |
| match fingerprint | map + จำนวนรอบ + สกอร์ (T−CT) + ชุด steam_id; ใช้ตัด validation match ออกจาก train (2026-11-05) |
| WP feature set | ชุด D แม้ CV log loss แพ้ชุด A 0.002 (< std ระหว่าง fold): A ให้ `time_left_post` ผิดทิศ; `ct_can_defuse` ใช้เกณฑ์ ≥ 10s เพราะ wp_states ยังไม่มีข้อมูล kit (2026-11-05) |
| WP training | weight = 1/แถว trainable ต่อรอบ, standardize feature, C จาก {0.01, 0.1, 1, 10}, แยก fold ตามแมตช์; แมตช์ FACEIT validation ใช้เช็ค round-start WP เท่านั้น ไม่ train (2026-11-05) |
| Impact ΔWP | แยก `delta_time` (wp_pre(e) − wp_after(ก่อนหน้า), steam_id null) ออกจาก `delta_event` เพราะ `ct_can_defuse` ทำให้ WP กระโดดตามนาฬิกา C4; round end ไม่มีส่วนเวลา (owner, 2026-11-05) |
| Impact damage share | damage แบบ sequential (`rws._sequential_enemy_damage`) ไม่ใช่ `dmg_effective` (owner, 2026-11-05) |
| Impact disconnect | death จาก `by_disconnect` ไม่ให้ใคร (แถว null, category `disconnect`) (owner, 2026-11-05) |
| Impact units | `rating_events.delta` = fraction; ×100 จุดเดียวที่ `credit.PCT` (impact_metrics + CLI); registry unit `pp` (2026-11-05) |
| Impact plant/explode | planter ได้ D, CT ที่รอดเสียแบ่งเท่ากัน (spec เดิมไม่ระบุฝั่งที่เสีย; ต้องมีเพื่อ zero-sum) (2026-11-05) |
