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

## ✅ Phase 2: Ratings (สูตรของเราเอง ไม่ใช้ชื่อ Leetify) — ปิดแล้ว (2026-11-05)
- [x] **`wp_states` builder + CLI `wp-states`** (impact-spec §6.3, ยังไม่ train, 2026-11-05): 1 แถว/state (freeze end, kill, plant, defuse, explode, round end) · features `t_alive`/`ct_alive`, `bomb_planted`, `time_left_s`, `equip_diff_k`, `map`, label `t_won` · column `trainable` แยกแถวที่ model ต้องทาย vs rule-fixed · ตัด validation match ด้วย fingerprint (map + จำนวนรอบ + สกอร์ + ชุด steam_id) · สร้าง `data/train_demos/manifest.csv` อัตโนมัติ ผล: 30/34 แมตช์ (ตัด 4 validation, 0 parse fail), 713 รอบ, 6,285 state (4,972 trainable); แมตช์/แมพ dust2 15 · mirage 6 · cache 4 · ancient 3 · inferno 2
- [x] **WP model v1 + CLI `train-wp`** (impact-spec §6.4 / §2.2.1, 2026-11-05): logistic L2 บน feature ที่ standardize (mean/std ใน `wp_model_v1.json`, predict numpy-only, sklearn เฉพาะ `train_wp.py` / extra `[train]`) · GroupKFold 5 ตามแมตช์ · ชุด D (A + map + alive_prod + ct_can_defuse) C=1: Brier 0.1472 log loss 0.4491 vs baseline 0.1638 / 0.4955 · reliability ห่าง ≤ 0.03 ทุกช่อง · FACEIT round-start WP T 62.3% (≈61) CT 54.4% (≈55)
- [x] **Impact credit + `rating_events` + metric `impact` + CLI `impact`** (impact-spec §3 / §6.5, 2026-11-05): แยก ΔWP จากเวลา (แถว `time` ไม่ให้ใคร) · kill แบ่ง 0.35/0.30/0.15/0.20 (`credit.yaml`, damage แบบ sequential จาก rws) · disconnect ไม่ให้ใคร · 9 หมวด + time + disconnect · invariant ผ่าน 4 แมตช์ (FACEIT, inferno, mirage, dust2) · เทียบ FACEIT Swing: Pearson All 0.88 / T 0.92 / CT 0.89, MAE 2.5 pp
- [x] Impact §6.6 ช่วงแรก (2026-11-05): config `time_credit: none | survivors` + CLI `--time-credit` (default none) · FACEIT: survivors ดีกว่า (Pearson All 0.883 → 0.907, MAE 2.50 → 2.32, ผลรวมทีม +19.76 vs FACEIT +19.57) · Leetify truth มีแค่ `leetify_rating` รวม (ไม่มี breakdown): Pearson inferno 0.99, mirage 0.89–0.91, dust2 0.98 (impact-spec §3.6)
- [x] FACEIT แมตช์ที่ 2 (mirage-4cb4009a, 2026-11-05): RWS off 10/30 (CT team b; สาเหตุยังไม่รู้ → rws คง calibrating) · Impact รวม 20 คน survivors Pearson All 0.929 / MAE 1.58 vs none 0.916 / 1.62 (impact-spec §3.6, §4)
- [x] validate-faceit / impact --faceit: จับคู่ผู้เล่นด้วย `match_players` (2026-11-05): key `"aliases": {"ชื่อในเกม": "ชื่อ FACEIT"}` (ไม่บังคับ) → ชื่อตรง/ไม่สนตัวพิมพ์ → elimination ในทีม (เหลือ 1↔1, พิมพ์ "matched by elimination") → ไม่งั้น FAIL พร้อมรายชื่อ (exit 1)
- [x] mirage-4cb4009a-faceit.json ใส่ `"aliases"` แล้ว (owner) → validate-faceit / impact จับคู่ครบ 10 คน
- [x] **Impact §6.6 ปิด: `time_credit` default = `survivors`** (2026-11-05, impact-spec §3.7): FACEIT 2 แมตช์ Pearson All 0.929 vs 0.916, MAE 1.58 vs 1.62; invariant ผ่าน 5 แมตช์

**งานค้างของ Phase 2** (ไม่ block Phase 3):
- [ ] RWS → `exact`: mirage-4cb4009a ต่าง ≤ 0.16 (CT team b 10/30), ไม่มีกฎที่ได้ 30/30 ทั้ง 2 แมตช์ (impact-spec §4) รอแมตช์ FACEIT ที่ 3
- [x] **WP model v2: defuse kit + defuse ที่กำลังกู้** (impact-spec §2.2.2, 2026-11-06): wp_states เพิ่ม `ct_has_kit`, `ct_defusing`, `ct_defusing_pre` (ไม่เพิ่ม state) · `ct_can_defuse` = เวลาพอตามคีม (5s / 10s) หรือกำลังกู้ทันเวลา · `wp_model_v2.json` = ตัวที่ใช้ (v1 เก็บไว้) · CV หลัง plant log loss 0.342 → 0.336, ช่วง 5–10s 0.557 → 0.273 · 4cb4009a r2 wp_pre ก่อน defuse 0.438 → 0.093 · FACEIT 4cb4009a CT Pearson 0.949 → 0.967 · validate-all + invariant 5 แมตช์ผ่าน
- [ ] เครดิตตอนเริ่มกู้ไปอยู่แถว `time` แบ่ง CT ที่รอดทุกคน (ไม่มี state `begin_defuse`, impact-spec §3.8)
- [ ] 4cb4009a ฝั่ง T Pearson 0.975 → 0.943 ตั้งแต่ใส่ kit: ดูอีกครั้งเมื่อมีแมตช์ FACEIT ที่ 3
- [ ] `ct_has_kit` เป็น feature (set E, ดีกว่า D ไม่เกิน noise): ลองใหม่ตอนมี 100 แมตช์
- [ ] WP mirage ต่าง FACEIT ~11 pp/รอบ ฝั่ง T (impact-spec §3.8) รอ demo mirage เพิ่ม
- [ ] เก็บ demo train ถึง 100 แมตช์ (ตอนนี้ 30) แล้ว train WP ใหม่ + ทบทวน damage share / ราคา death
- [ ] (เลื่อน) Aim / Utility / Positioning Score: แยกตามกลุ่มปืน (sniper / rifle / pistol) ไม่ให้ metric ที่เป็น n/a ดันคะแนน และบอกความมั่นใจตามขนาดตัวอย่าง (บทเรียนจาก Aim 100 ของ Leetify ในแมตช์ที่ใช้ AWP)

## ▶️ Phase 3: Backend — current (เริ่ม 2026-11-05)
แผนเต็ม: [`design/backend.md`](design/backend.md) (schema, R2 layout, jobs, API, auth, privacy, recompute) · เกณฑ์ผ่านของแต่ละช่วง: backend.md §12
- [x] **3.0** แผน + schema: `docs/design/backend.md` + data-model §1 / §2.3 / §2.5 / §7 (2026-11-06)
- [x] **3.1** `server/iaserver/pipeline.run_match` + bundle (`python -m iaserver bundle`, `data/bundles/`) + refactor ใน `impactagent` ที่ไม่เปลี่ยน logic (`parse/io.py` write_tables, `match_tables` / `compute_match_metrics(p, events)`, `read_state_snapshots` + `build_wp_states(p, snapshot)`) + `state_ticks` (รวม `balance`) / `defuse_starts` / `cvars` / `header.json` (2026-11-06): เทียบ golden จาก HEAD 5 แมตช์ผ่านหมด (bundle 65/65), `validate-all` log เหมือนเดิม · 13–23 s/แมตช์, peak RSS ≤ 0.73 GB, bundle 0.31–0.43 MB (backend.md §6.4)
- [ ] **3.1b** replay 8 Hz ใน bundle (ตำแหน่ง, ทิศ, HP, อาวุธ, alive, flags + เส้นทางระเบิด, 1 ไฟล์ต่อรอบ)
- [ ] **3.2** `recompute(bundle)` ไม่มี demo: ผลตรงกับรอบที่มี demo ทุกแมตช์
- [ ] **3.1c** (หลัง 3.2 ก่อน 3.3) metric function คืน numerator / denominator → `metric_values` / jsonb `[value, num, den]` (ตอนนี้ num/den = null)
- [ ] **3.3** Supabase migrations (local) + loader bundle → PG: scoreboard ตรงกับ `compute_match_metrics`
- [ ] **3.4** R2: bundle + manifest + lifecycle `incoming/` (2 วัน) / `failed/` (7 วัน)
- [ ] **3.5** Worker pull loop + state machine + retry / reaper + `job_errors` (fault `input` / `infra` / `ours`)
- [ ] **3.6** API upload flow + `upload_requests`: หลายคนอัปไฟล์เดียวกัน → 1 job ทุกคนได้แมตช์ · `.dem` / `.dem.bz2` ของแมตช์เดียวกัน → แมตช์เดียว
- [ ] **3.7** Steam OpenID + `auth.users` (Admin API) + JWT cookie + CORS / CSRF
- [ ] **3.8** Endpoints match / player / privacy (redact) / admin (failed jobs, retry)
- [ ] **3.9** docker-compose บน laptop (api + worker + cloudflared) ผ่าน Cloudflare Tunnel `api.tammapol.com`: same-site cookie ใช้ได้จากโดเมนจริง
- [ ] **3.10** Recompute job + `/admin/recompute` (version ใหม่, rollback ได้)

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
| Backend v0.1 | `docs/design/backend.md` (owner 2026-11-06): Steam OpenID ใน FastAPI → `auth.users` ผ่าน Admin API + JWT cookie ของเราเอง · R2 presigned PUT (`.dem` / `.dem.bz2` / `.dem.gz` / `.dem.zst`, ≤ 512 MB, 10/วัน/user) · queue = ตาราง `jobs` + worker pull · metric ใน PG = jsonb ต่อ (match, player), long format อยู่ Parquet · `kills` Parquet อย่างเดียว · แมตช์ unlisted, profile เฉพาะคนที่ login, มีทางขอลบข้อมูล · replay 8 Hz เก็บตั้งแต่ parse (3.1b) · demo ที่ fail เก็บ 7 วันใน `failed/` · Gemini free tier ช่วง beta (เขียนใน Privacy Policy) · `server/` แพ็กเดียว |
| Pipeline 3.1 | `match_tables()` คืน metrics + player_rounds + clutches (กฎกรอง `post_match` ที่เดียว) · package `server/iaserver/` · bundle ใน `data/bundles/` (gitignored) · num/den เป็นช่วง 3.1c · `state_ticks` เก็บ `balance` · cvars เก็บเป็น `cvars.parquet` (JSON ของ FACEIT 220 KB) (owner 2026-11-06) |
| Hosting beta | API + worker ใน docker-compose เดียวกันบน laptop + Cloudflare Tunnel (`api.tammapol.com`) → ย้ายไป VPS ทั้งคู่เมื่อคนเยอะ · upload ไป R2 ตรง ไม่ผ่าน Tunnel (limit body 100 MB) (owner 2026-11-06) |
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
| WP feature set | ชุด D แม้ CV log loss แพ้ชุด A 0.002 (< std ระหว่าง fold): A ให้ `time_left_post` ผิดทิศ; v1 `ct_can_defuse` ใช้เกณฑ์ ≥ 10s เพราะ wp_states ยังไม่มีข้อมูล kit (2026-11-05) |
| WP model v2 | `wp_model_v2.json` = ตัวที่ใช้ (v1 เก็บไว้ไม่เขียนทับ) · ชุด D เดิม แต่ `ct_can_defuse` = เวลาพอ (5s มีคีม / 10s ไม่มี) **หรือ** มี defuse ที่กำลังกู้ทันเวลา · set E (`ct_has_kit` เป็น feature) ไม่ใช้เพราะดีกว่าไม่เกิน noise (owner, 2026-11-06) |
| Defuse ที่กำลังกู้ | begindefuse ที่เริ่มตอนเวลาพอสำหรับคีมของคนกด + ยังไม่จบ (หมดเวลากู้ / defused / ตาย / กดใหม่ / abort) + คนกู้ยัง `is_defusing` ณ tick · CS2 ไม่ยิง `bomb_abortdefuse` จึงต้องใช้ `is_defusing` · เก็บเป็น flag ใน state เดิม (`ct_defusing`, `ct_defusing_pre`) ไม่เพิ่ม state เพื่อไม่ต้องแก้ credit / invariant (2026-11-06) |
| WP training | weight = 1/แถว trainable ต่อรอบ, standardize feature, C จาก {0.01, 0.1, 1, 10}, แยก fold ตามแมตช์; แมตช์ FACEIT validation ใช้เช็ค round-start WP เท่านั้น ไม่ train (2026-11-05) |
| Impact ΔWP | แยก `delta_time` (wp_pre(e) − wp_after(ก่อนหน้า), steam_id null) ออกจาก `delta_event` เพราะ `ct_can_defuse` ทำให้ WP กระโดดตามนาฬิกา C4; round end ไม่มีส่วนเวลา (owner, 2026-11-05) |
| Impact damage share | damage แบบ sequential (`rws._sequential_enemy_damage`) ไม่ใช่ `dmg_effective` (owner, 2026-11-05) |
| Impact disconnect | death จาก `by_disconnect` ไม่ให้ใคร (แถว null, category `disconnect`) (owner, 2026-11-05) |
| Impact units | `rating_events.delta` = fraction; ×100 จุดเดียวที่ `credit.PCT` (impact_metrics + CLI); registry unit `pp` (2026-11-05) |
| Impact time credit | default `time_credit: survivors` (คนรอดแต่ละฝั่งแบ่ง delta_time) แทน `none`: FACEIT 2 แมตช์ Pearson 0.929 vs 0.916, MAE 1.58 vs 1.62, ผลรวมทีมใกล้กว่า; Leetify สูสี (owner, 2026-11-05) |
| Impact plant/explode | planter ได้ D, CT ที่รอดเสียแบ่งเท่ากัน (spec เดิมไม่ระบุฝั่งที่เสีย; ต้องมีเพื่อ zero-sum) (2026-11-05) |
