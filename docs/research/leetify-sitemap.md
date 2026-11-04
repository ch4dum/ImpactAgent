# Leetify Sitemap & Page Structure

แผนผังเว็บ Leetify สำหรับใช้เป็น reference ตอนออกแบบ ImpactAgent สำรวจเมื่อ 2026-11-05

**สถานะ:** ✅ สำรวจแล้ว · ⏳ ยังไม่ได้สำรวจ · 🔒 ต้อง login

---

## 1. ฝั่ง Logged-out (คนนอก)

### 1.1 Landing `/`
Title: *"Leetify – CS2 Stats & Accomplishments"*

| ลำดับ | Section | สาระ |
|---|---|---|
| 1 | Hero | "Track Your Counter-Strike Performance" + ปุ่ม **Sign Up For Free** |
| 2 | ตัวอย่าง match card | สกอร์ (VICTORY 13:9), แมพ, MR12, วันที่, Achievements, Highlights |
| 3 | Celebrate your unique accomplishments | Personal best เช่น "HIGHEST KILLS: 37" (gamification) |
| 4 | Track your true performance | ขาย **Leetify Rating** ว่าบอกได้ว่าใครแบก/ใครเบท มากกว่า scoreboard ในเกม |
| 5 | Compare with your friends | Profile card ของ s1mple vs ZywOo + ปุ่ม COMPARE |
| 6 | Automatic Highlights | คลิปไฮไลต์อัตโนมัติ (เช่น "ROUND 5 AK-47 Ace") |
| 7 | Get instant feedback | Match report ส่งให้อัตโนมัติไม่กี่นาทีหลังจบเกม + แจ้งเตือนเมื่อคนที่เคยเล่นด้วยโดนแบน |
| 8 | Leetify works with | Matchmaking, FACEIT, Gamers Club, CYBERSHOKE, Esplay |

**Profile card** (ใช้ซ้ำทั้งเว็บ ทั้ง landing และ hover ที่ชื่อผู้เล่นในหน้าแมตช์):
Premier rating · AIM (0–100) · UTILITY (0–100) · POSITIONING (0–100) · CLUTCHING (±) · OPENING DUELS (±) · LEETIFY RATING (±, พร้อม label Great/Average/Poor) · RECENT RESULTS (W/L/T 5 เกมล่าสุด, กดแล้วไปหน้าแมตช์) · ปุ่ม PROFILE / COMPARE · ลิงก์ Steam / FACEIT

### 1.2 Navigation
- **Tools (dropdown):** Discord Bot `/discord-bot` · Monthly Bans `/bans` · Spray Patterns `/cs2-spray-patterns` · Public Data Library `/data-library` · Leaderboards `/public/premier-leaderboards/valve`
- **อื่นๆ:** Careers · Blog · Log In · Sign Up
- **Footer:** Pioneers Wall · Terms · Privacy · Steam group · Twitter · Discord · Email · YouTube

### 1.3 Auth
- `/auth/login`, `/auth/signup` (มี `?t=<return path>` ไว้เด้งกลับหน้าเดิมหลัง login)

### 1.4 Public pages (เปิดได้โดยไม่ต้อง login)
- `/public/match-details/{id}/...` เป็นหน้าแมตช์สำหรับแชร์ ส่วน `/app/...` จะ redirect มาที่นี่ถ้าไม่ได้ login
- คนนอกจะเห็นแถบ "log in to access Achievements and Highlights"
- `/app/profile/{steam64}` และ `/app/compare/{steam64}/{steam64}` ⏳

---

## 2. หน้าแมตช์ `/app/match-details/{matchId}/{tab}` ✅ (โครงสร้าง)

**Header (ทุก tab):** VICTORY/DEFEAT + สกอร์ · วันเวลา · data source (ไอคอน MM/FACEIT) · MR12 · server region (SINGAPORE) · แมพ · **Win Rate Forecast** · เมนู ⋮ (Add Labels [PRO], Share this Match)

**Win Rate Forecast (dropdown):** โอกาสชนะ/แพ้ที่คาดไว้ก่อนเกม (59% / 37%) · average rating ของแต่ละทีม (Premier) · rating spread · **expected round differential** เป็นการแจกแจงความน่าจะเป็นของสกอร์ (13–≤7, 13–8, … , OT, … , ≤7–13)

### Tabs
| Tab | Path | Sub-tabs | สถานะ |
|---|---|---|---|
| Overview | `overview` | — | ✅ |
| Match Details | `details-*` | General · Timeline · Aim · Utility · Activity · Trades · Opening Duels · Clutches | 🟡 General แล้ว |
| Head to Head | `head-to-head` | | ⏳ |
| Rating Breakdown | `rating-breakdown` | | ⏳ |
| Map Zones | `map-zones` | | ⏳ |
| 2D Replay | `2d-replay` | | 🔒 PRO |

### Overview
- **Top 3 players** ตาม Leetify Rating (ถ้วยทอง/เงิน/ทองแดง + รูป agent skin)
- **Scoreboard แยก Winning/Losing team** แต่ละทีมมีเฟือง ⚙️ ให้เลือก column เองได้ และ sort ได้ทั้งแบบ "individually" หรือ "by team"
- Default columns: Rating · Personal Performance · HLTV Rating · K/D · ADR · Aim …
- ⭐ ติดค่าที่ดีที่สุดในแมตช์ และใช้สีของตัวเลขบอกดี/แย่

**Metric ที่เลือกเป็น column ได้ทั้งหมด (catalogue หลัก):**
- **RATINGS:** Aim Rating · HLTV Rating 1.0 · Leetify Rating (CT / T / รวม) · Personal Performance · Positioning Rating · Utility Rating
- **GENERAL:** Assists · ADR · Deaths · KAST · Kill Difference · K/D · Kills · Rounds Survived · Total Damage · Rounds with 2K/3K/4K/5K · **Wasted Magazine %**
- **AIM:** Accuracy (All Shots) · Accuracy (Enemy Spotted) · Crosshair Placement · **First Bullet Accuracy** · Headshot Accuracy · HS Kill % · Proper Counter-Strafing · Shots Fired · Spray Accuracy · Time to Damage · **Time to Kill**
- **POSITIONING:** CT/T Opening Duel Attempts % · Success % · Traded % · CT Opening Duels won without being traded · Trade Kill Attempts/Opportunities/Success · Traded Death Attempts/Opportunities/Success
- **UTILITY:** Damage to Enemies/Teammates per HE · Enemies/Friends Flashed per Flashbang · Flash Blind Duration per Flashed Enemy · Flashbangs Leading to Kills · Total Enemies Flashed · Total Enemies Flashed Duration · Total HE Damage · Total Molotov Damage · Unused Utility on Death · **Utility Quality Rating** · **Utility Quantity Rating**

> ตัวหนา = metric ที่ยังไม่อยู่ใน `docs/metrics/leetify-metrics-spec.md` ต้องเพิ่ม

### Match Details → General
Columns: Kills · Assists · Deaths · K/D · ADR · KAST · 2K · 3K · 4K · 5K · HLTV Rating · Rating · Personal Performance (แยกทีม)

---

## 3. ฝั่ง Logged-in 🔒 ⏳
- Dashboard / หน้าแรกหลัง login
- รายการแมตช์
- Profile ของตัวเอง + trend
- Compare
- Achievements, Highlights

---

## 4. ข้อสังเกตสำหรับ ImpactAgent
- **Shareable public match URL** สำคัญมาก ทำให้เว็บโตแบบ viral (เพื่อนส่งลิงก์ให้กันดู) MVP ควรมี
- **Profile card** เป็น component ที่ใช้ซ้ำทั้งเว็บ ควรออกแบบ data model ของมันตั้งแต่แรก
- **Column chooser** แสดงว่า metric ทั้งหมดควรอยู่ใน registry เดียว (ชื่อ, หมวด, หน่วย, ทิศทางดี/แย่, format) เพื่อให้ UI สร้าง table ได้อัตโนมัติ และ LLM coach อ่าน registry เดียวกันเพื่อรู้ว่าแต่ละ metric หมายถึงอะไร
- **Win Rate Forecast ก่อนเกม** ต้องใช้ rating ของผู้เล่นจากหลายแมตช์ จึงไม่ใช่งาน MVP
- **จุดต่างที่เราจะชนะได้:** Leetify ให้ "ตัวเลข" แต่ไม่มีใครอธิบายว่าเลขเหล่านั้นแปลว่าอะไรกับ *ตัวเรา* ตรงนี้คือที่ LLM coach เข้ามาแทน
