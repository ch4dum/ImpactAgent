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
- [x] Metric registry (`impactagent/metrics/registry.yaml`): 43 metric (39 exact, 4 calibrating); `validate-all` เช็คว่า registry ครบ/ถูก format และ calibrating ไม่ gate
- [ ] Head Accuracy (ไม่ต้องใช้ visibility)
- [ ] Engagements + visibility v0 (`spotted`) → Aim: spotted accuracy, TTD, crosshair, counter-strafe, spray, TTK, first bullet
- [ ] Visibility v1 (raycast กับ map geometry) ทำเฉพาะถ้า v0 คลาดจาก Leetify มาก
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
| ชื่อ product | ยังไม่ตัดสินใจ (ห้ามมี CS2 / Counter-Strike) |
| LLM | Gemini API free tier + export ให้ user ใช้ AI ของตัวเอง |
| Buy type thresholds | ยังไม่ตัดสินใจ (Leetify ไม่เปิดเผย) |
| Visibility | เริ่มที่ `spotted` แล้วค่อยดูว่าต้อง raycast ไหม (`approximate_spotted_by` ให้ trade opportunity ตรงแค่ ~60%) |
| Trade window | 4.0s (ช่วงที่ข้อมูลยอมรับ [3.48, 4.47) s) |
| validate gating | gate core metric + opening duels + clutches; metric ที่ registry ตั้ง `status: calibrating` (ตอนนี้ trade opp/att) รายงานแต่ไม่ fail |
| Parse limits | .dem หลังแตก ≤ 1 GiB (`MAX_DEMO_BYTES`), parse ≤ 300s (`PARSE_TIMEOUT_SECONDS`); เวลาแตกไฟล์ไม่นับใน timeout (คุมด้วยขนาดแทน) |
