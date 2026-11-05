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

## ⏳ Phase 1: Metrics engine (ครบหนึ่งแมตช์)
- [x] Trades: `trade_windows`, succeeded, opening traded %, clutches
- [ ] Trade opportunities / attempts: ตอนนี้เป็นสมมติฐาน (ตรง ~60%) → calibrate ใหม่หลังมี visibility
- [x] Metric registry (`impactagent/metrics/registry.yaml`): 53 metric (42 exact, 11 calibrating); `validate-all` เช็คว่า registry ครบ/ถูก format และ calibrating ไม่ gate
- [x] Head Accuracy: นับต่อนัด ไม่นับ AWP / ลูกซอง; นัดที่ทะลุหัวไปโดนคนที่ 2 ไม่นับเป็นหัว (inferno 10/10, mirage 10/10)
- [x] `shots` features + `engagements` (`impactagent/parse/aim.py`) + Aim metrics (`impactagent/metrics/aim.py`); core รวม **inferno 305/305, mirage 350/350**
  - exact: `shots_fired` (ไม่นับลูกซอง และนัดใน tick ที่คนยิงตาย; Mirage holdout เจอทั้งสองกฎ), `accuracy_all`, `accuracy_head`
  - calibrating (ตรงราย player inferno / mirage): spotted acc 3/10, 6/10 · counter-strafe 2/9, 3/9 · spray 0/7, 3/8 · first bullet 1/10, 0/10 · TTK 1/10, 0/10 · TTD 0/10, 0/10 · crosshair 0/10, 0/10
  - Holdout Mirage ก่อนแก้โค้ด: core aim 9/20 (shots_fired 3/10, accuracy_all 6/10), calibrating 15/77
- [ ] Aim calibrating: TTD / crosshair ของเราต่ำกว่า Leetify ทุกคน (เราเห็นศัตรูช้ากว่า) → ตรวจว่า mesh ของ awpy มี player clip / prop ที่ไม่บังสายตาจริงไหม, ลองจุดเป้าแบบ hitbox; spray ของ Leetify น่าจะไม่ใช่ hit/shot (yyh 0.83 ทั้งที่ accuracy 0.11)
- [x] **Visibility module** (`impactagent/visibility/`, 2026-11-05): interface เดียว backend `spotted` (ของเกม) / `raycast` (awpy mesh) + lag window 7 tick + ควันทรงกลม + FOV 50°; `python -m impactagent visibility DEMO...` รายงานผล
  - kill ปกติที่ "เห็น" (raycast เต็ม): inferno 72/72, mirage 150/152; ผ่านควัน: 0/7, 2/7; `spotted` ของเกมเห็นแค่ ~75% ของ kill ปกติ
  - ความเร็ว: raycast ~29k คู่-tick/วินาที (inferno ทุกคู่ศัตรูทุก 4 tick = 248k คู่ ใน 8.5s + อ่าน tick 5.3s)
- [x] Visibility v1 (raycast กับ map geometry)
  - [x] Spike awpy 3.1.1 `VisibilityChecker` (`scripts/visibility_spike.py`, ยังไม่เข้า metrics): kill ปกติ "เห็น" 95.8% (inferno 69/72) / 95.4% (mirage 145/152), penetrated เห็นแค่ 1/2 และ 1/8, ~3-4 µs ต่อ ray, mesh โหลด < 0.1s
  - [x] Kill ที่ "ไม่เห็น" (~4-5%) มาจาก lag compensation: ย้อนตำแหน่งคนตาย 2-7 tick แล้วเห็นครบ 72/72 และ 152/152; ไม่มีจุดชน mesh ใกล้ตัว < 16 unit (ไม่ใช่ player clip); eye height ใช้ `m_flDuckViewOffset` (demo ไม่มี `m_vecViewOffset`); ย้อนแล้ว penetrated "เห็น" เพิ่มจาก 1/8 เป็น 2/8 บน mirage
- [ ] Round buy type (pistol / eco / semi-eco / force / full) + Map Zones (`last_place_name`)

## ⏳ Phase 2: Ratings (สูตรของเราเอง ไม่ใช้ชื่อ Leetify)
- [ ] Impact Rating: win-probability model + breakdown 9 หมวด
- [ ] Aim / Utility / Positioning Score: แยกตามกลุ่มปืน (sniper / rifle / pistol) ไม่ให้ metric ที่เป็น n/a ดันคะแนน และบอกความมั่นใจตามขนาดตัวอย่าง (บทเรียนจาก Aim 100 ของ Leetify ในแมตช์ที่ใช้ AWP)

## ⏳ Phase 3: Backend
- [ ] Supabase: Postgres (ตาราง core) + Auth (Steam OpenID ผ่าน backend เรา)
- [ ] เก็บ event ละเอียดเป็น Parquet; ไฟล์ `.dem` ลบทิ้งหลัง parse
- [ ] Upload: presigned URL รับ `.dem.bz2` → queue → worker (parse + metrics)
- [ ] FastAPI

## ⏳ Phase 4: AI Coach
- [ ] LLM layer แบบเปลี่ยน provider ได้ (เริ่มที่ Gemini free tier)
- [ ] **Export สำหรับ AI ของ user เอง:** ไฟล์ JSON/Markdown สรุปแมตช์ + prompt ให้ import ไปใช้กับ ChatGPT / Claude / Gemini (ไม่มีต้นทุน)
- [ ] Tools: query `metric_values` / `engagements` + NL2SQL read-only
- [ ] Match report แบบเล่าเรื่อง (เกินกว่า "Your Match" ของ Leetify)
- [ ] Eval set: ชุดคำถามวัดคุณภาพคำตอบ

## ⏳ Phase 5: Frontend
- [ ] ตัดสินใจ stack + mockup
- [ ] Match page, Your Match + แชท AI, หน้าอัปโหลด, profile

## ⏳ Phase 6: Deploy
- [ ] Subdomain บน `tammapol.com` (Cloudflare) เช่น `impactagent.tammapol.com` จนกว่าจะได้ชื่อ product
- [ ] VPS สำหรับ API + worker, login ด้วย Steam
- [ ] Rate limit / คุมค่า LLM, Terms / Privacy

## หลัง MVP
ดึงแมตช์อัตโนมัติด้วย share code · benchmark ตาม rank · Focus Areas · 2D Replay · Highlights

---

## การตัดสินใจ
| เรื่อง | สถานะ |
|---|---|
| Database | **Supabase** (Postgres + Auth) |
| Domain | **tammapol.com** (Cloudflare) ใช้ subdomain ไปก่อน |
| Branches | `main` = rebuild (เดิมชื่อ `v2`, default บน GitHub) · `v1-draft` = prototype เดิม (เดิมชื่อ `main`) ไว้อ้างอิงเท่านั้น (2026-11-05) |
| ชื่อ product | ยังไม่ตัดสินใจ (ห้ามมี CS2 / Counter-Strike) |
| LLM | Gemini API free tier + export ให้ user ใช้ AI ของตัวเอง |
| Buy type thresholds | ยังไม่ตัดสินใจ (Leetify ไม่เปิดเผย) |
| Visibility | **raycast เป็นค่าหลัก** `spotted` ยังสลับใช้ได้ (`spotted` เห็น kill ปกติแค่ ~75%) (2026-11-05) |
| Lag compensation | **window คงที่ 7 tick** (เป้าหมายตำแหน่งใดก็ได้ใน 7 tick ล่าสุด) ไม่ย้อนตาม ping: tick ที่ต้องย้อนไม่สัมพันธ์กับ ping ของคนยิง (rank corr 0.01, 64 hit, ping 13–57ms) (2026-11-05) |
| Aim shot set | นัดที่นับใน accuracy ทุกตัว = ปืน (ไม่นับมีด / taser / ระเบิด / **ลูกซอง**) ทั้งช่วงรอบรวมหลัง round_end ยกเว้นนัดใน tick ที่คนยิงตาย; hit = ทำ damage ศัตรูใน tick เดียวกัน (2026-11-05) |
| Engagement v1 | สร้างจาก damage: สแกนย้อนทีละ tick ขณะ A เห็น B (gap ≤ 8 tick, ≤ 2.5s) ยังไม่มี engagement ที่ไม่มี damage (2026-11-05) |
| Smoke | ทรงกลม R 144, ศูนย์กลาง +32 จากจุดระเบิด, บล็อกตั้งแต่ระเบิด +0.5s ถึง `smokegrenade_expired`; calibrate บน inferno (2026-11-05) |
| Trade window | 4.0s (ช่วงที่ข้อมูลยอมรับ [3.48, 4.47) s) |
| validate gating | gate core metric + opening duels + clutches; metric ที่ registry ตั้ง `status: calibrating` (ตอนนี้ trade opp/att) รายงานแต่ไม่ fail |
| Map geometry | awpy-data `.mesh` (`pip install -e .[visibility]`, cache `~/.awpy/<ClientVersion>`, ไม่ commit) เลือก release ตาม `csgo_v<build>` ใน header ของ demo (2026-11-05) |
| Parse limits | .dem หลังแตก ≤ 1 GiB (`MAX_DEMO_BYTES`), parse ≤ 300s (`PARSE_TIMEOUT_SECONDS`); เวลาแตกไฟล์ไม่นับใน timeout (คุมด้วยขนาดแทน) |
