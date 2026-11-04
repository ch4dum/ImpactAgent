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
- `/app/profile/{steam64}` (redirect ไป `/@{name}`) และ `/app/compare/{steam64}/{steam64}`

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

## 3. ฝั่ง Logged-in (`/app/...`) ✅

### 3.1 Sidebar navigation
| กลุ่ม | เมนู | Path |
|---|---|---|
| หลัก | Home · **Dashboard** | `/home` · `/app` |
| Matches | Matches · Sessions | `/app/matches/list` · `/app/matches/session` |
| Social | My Clubs | `/app/clubs` |
| Stats (ภาพรวมหลายแมตช์) | General · Maps · Aim · Utility | `/app/general` · `/app/maps` · `/app/aim` · `/app/utility` |
| ฝึก/พัฒนา | Training (NEW) · **Focus Areas** | `/app/training` · `/app/focus-areas` |
| สะสม | Highlights · Achievements | `/app/highlights` · `/app/achievement-collection/{steam64}` |
| อื่นๆ | Leaderboards · **Ask AI** · Free Pro (referral) · Data Library | `/app/premier-leaderboards/valve` · `/app/ask` · `/app/referrals` |
| User menu | Profile · Compare · Account Settings · Data Sources · Support · Progress Reports (รายไตรมาส) · Yearly Recap | `/app/profile/{steam64}` → `/@{name}` · `/progress-report/{yyyy}/q{n}/{steam64}` · `/{yyyy}/{steam64}` |

### 3.2 Dashboard `/app`
1. **Recent Matches:** การ์ดต่อแมตช์ แสดง VICTORY/DEFEAT, สกอร์, วันเวลา, จำนวน achievements/highlights, Rating, K/D และ "สถิติเด่น 1 ตัว" ที่หมุนเปลี่ยนไปตามแมตช์ เช่น Head Accuracy หรือ Spotted Accuracy
2. **Focus Areas:** จุดอ่อน 3 อย่าง แต่ละอย่างมี MY RATING (0–100 + label) → GOAL (ค่าเป้าหมาย + label) + คำแนะนำสั้นๆ
3. **Performance:** เทียบตัวเรา vs GOAL (rank bracket เช่น 25,000+)
4. **Recent Form / Consistency:** Leetify Rating รวม / T / CT เทียบกับ bracket ("ON PAR") + กราฟ Rating & Win Rate
5. **Recent Top Highlights**

### 3.3 Matches `/app/matches/list`
- **Filter bar (ใช้ร่วมกันทุกหน้า stats):** Current vs Previous period (30 games) · CS:GO/CS2 · Labels · Maps · Data Sources · Partied with · **Compare to `<rank bracket>`**
- **ตาราง:** Map · Date · Score · Rank (+/− Premier) · Rating · Kills · Deaths · K/D · Aim · Utility · Achievements · Highlights · Source
- **ปุ่ม Upload Demo** · Post-match Journal (PRO: จด sleep/caffeine/warm-up แล้วดูผลต่อ win rate)

### 3.4 Sessions `/app/matches/session`
รวมแมตช์ที่เล่นต่อเนื่องเป็น 1 session (W:L, เวลารวม) + การ์ดเพื่อนที่ party ด้วย แต่ละคนมี Leetify Rating (รวม/T/CT) + **role/achievement label** เช่น INITIATOR, T SPECIALIST, UTILITY BELT, HARD CARRY, MVP, OVERPERFORMER, CLUTCH

### 3.5 Stats pages (หลายแมตช์)
**General** `/app/general`
- Split: Overall / T / CT และแยกตาม **economy**: Pistol · Eco · Semi-Eco · Force · Full Buy
- Win rate · Leetify Rating · HLTV Rating · K/D · kills/round · deaths/round · ADR · HS Kill % โดยทุกค่าแสดงคู่กับ previous period
- Multikills (ต่อรอบ + รวม) · Opening Duels (Traded / Attempts / Success / Rating) · Clutching (1v1–1v5: win rate, save rate, avg kills) · Rounds survived · Best Weapon

**Aim** `/app/aim`
- Recoil control: ภาพ spray pattern ของเรา (AK-47, M4A4, M4A1-S; ปืนอื่นต้อง PRO)
- การ์ดต่อ metric: **label (Great/Average/Subpar/Poor) · ค่าเฉลี่ยของ bracket · current period · previous period · "View skill details" · ลิงก์ไปโหมดฝึกที่ตรงกับจุดอ่อน** (เช่น Counter-strafing → Tradefire mode)
- Metrics: Headshot Accuracy · Accuracy (Enemy Spotted) · Accuracy (All Shots) · Spray Accuracy · Proper Counter-Strafing · Crosshair Placement · Time to Damage
- ลิงก์ไป Map Zones Tool

**Utility** `/app/utility` ใช้การ์ดแบบเดียวกัน: Flashbangs Leading to Kills · Enemies/Friends Flashed per Flashbang · Flash Blind Duration · Damage to Enemies/Teammates per HE · Unused Utility on Death + Map Flash Tool

**Maps** `/app/maps` ต่อแมพ: Win rate · จำนวนเกม · % ต่างๆ เทียบ Current/Previous/Benchmark (น่าจะเป็น T/CT round win %) + ปุ่ม Zones / Flashes

### 3.6 Profile `/@{name}`
- Header: Following/Followers · **Ranks** (Premier/FACEIT/Competitive/Wingman: current + best + Rank History) · Steam info (account age, level, total matches, total hours) · Crosshair · Gear & Settings · Party size
- Sub-tabs: Overview · Match History · Rank History · Teammates · Maps
- Overview: Leetify Rating · Win rate · K/D · KAST และ **Rating แบบ percentile ต่อ rank bracket** เช่น "Aim 93 = Better than 93% of players · คนใน bracket 20,000–24,999 เฉลี่ย 68" พร้อม histogram ว่าเราอยู่ช่วง 50–60 / 60–70 / … กี่ % ของแมตช์
- Last 30 Matches · Top Highlights · Personal Bests

### 3.7 Focus Areas `/app/focus-areas/{key}`
- Active 3 อย่าง + Recent (เช่น Spray Control, Utility Quantity, HE Usage, Flashbang Usage on <map>, CT Side on <map>, Counter-Strafing, Trade Fragging, Clutching, Crosshair Placement)
- แต่ละหน้า: "What is …" · MY RATING → GOAL · ข้อมูลของเรา · กราฟ progress · บทความสอน
- key ที่เห็น: `sprayControl`, `usingUtility`, `heUsage`

### 3.8 Ask AI `/app/ask` 🔒 PRO
- Chat ถามเรื่องแมตช์ของตัวเองเป็นภาษาธรรมชาติ
- ตัวอย่างคำถาม: "How many CS matches have I played each year?", "Show me every match where I got two zeus kills.", "What is my win rate when I get 30 kills?", "How often did I flash my teammates in my last 3 matches?"
- → เป็นแนว **NL2SQL บนสถิติหลายแมตช์** (นับ/กรอง/รวม) ไม่ใช่ coach ที่อธิบายว่าทำไมแพ้หรือควรแก้อะไร

### 3.9 อื่นๆ
- **Data Sources:** Steam (ระบุตัวตน) · Matchmaking (ผ่าน **share code** ดึงอัตโนมัติ) · FACEIT · CYBERSHOKE · Gamers Club · **Manual Demo Upload: FACEIT ฟรี แต่ demo ทั่วไปต้อง PRO**
- **Achievements:** หมวด Aim, Clutching, Impact, Results, Style, Tactics, Utility, Weapons, Memes, Secret, Personal Bests เป็นการ์ดแชร์ได้ มีข้อความกวนๆ
- **Highlights:** คลิปอัตโนมัติ (2K/3K/4K/Ace) filter ตามอาวุธ/แมพ และ pin ไว้บน profile ได้
- **Training:** ทำร่วมกับ SCL.gg มีเซิร์ฟเวอร์ฝึก Solo / Practice / Retake / Scrim / Surf (PRO)

---

## 4. ข้อสังเกตสำหรับ ImpactAgent
- **โอกาสที่ชัดที่สุด:** Leetify ให้อัปโหลด `.dem` เองเฉพาะ PRO และ Ask AI ก็เป็น PRO เราทำ **"อัป .dem ฟรี + AI coach ฟรี"** ได้ เป็นจุดขายตั้งแต่วันแรก
- **ตำแหน่งของ AI เรา:** Ask AI ของ Leetify ตอบคำถามเชิงนับ/กรอง ("กี่ครั้ง", "แมตช์ไหน") ของเราควรเป็น **coach ที่อธิบายเหตุผล**: ทำไมรอบนี้แพ้ ตายเพราะ positioning หรือ aim ควรฝึกอะไร โดยอ้าง round/tick จริงได้ (ส่วน NL2SQL ทำได้ด้วยเพราะเป็นทางถนัดของเรา)
- **Benchmark ต่อ rank bracket** อยู่ในทุกหน้า (label Great/Poor, percentile) ต้องมีข้อมูลจากผู้เล่นจำนวนมาก ช่วงแรกใช้ benchmark จาก pro demos หรือ demo ที่ user อัปขึ้นมาได้ก่อน
- **การ์ด metric มาตรฐาน** (ค่า · label · benchmark · previous · skill details · วิธีฝึก) ใช้ซ้ำทั่วเว็บ → metric registry ต้องมีฟิลด์ `benchmark`, `direction`, `how_to_improve`
- **Economy split** (Pistol/Eco/Semi-Eco/Force/Full Buy) ต้องจัดประเภทรอบตาม equipment value ตั้งแต่ตอน parse
- **Shareable public match URL** สำคัญมาก ทำให้เว็บโตแบบ viral (เพื่อนส่งลิงก์ให้กันดู) MVP ควรมี
- **Profile card** เป็น component ที่ใช้ซ้ำทั้งเว็บ ควรออกแบบ data model ตั้งแต่แรก
- **Column chooser** แสดงว่า metric ทั้งหมดควรอยู่ใน registry เดียว (ชื่อ, หมวด, หน่วย, ทิศทางดี/แย่, format) เพื่อให้ UI สร้าง table ได้อัตโนมัติ และ LLM coach อ่าน registry เดียวกัน
- **Gamification** (achievements, highlights, personal bests, recaps) คือสิ่งที่ทำให้คนกลับมาเว็บ แต่ไม่ใช่ MVP
- **ไม่ใช่ MVP:** Win Rate Forecast, Training servers, Clubs, Highlights (ต้อง render วิดีโอ)
