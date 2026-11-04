# Leetify Metrics Spec (Phase 0)

แกะ metric ของ Leetify ทีละตัว: Leetify นิยามว่าอะไร → ต้องดึงอะไรจาก `.dem` → เราจะคำนวณยังไง → อะไรที่ยังไม่รู้

**แหล่งข้อมูล**
- [Leetify Stats Glossary](https://leetify.com/blog/leetify-stats-glossary) — นิยามทางการ
- [Leetify Rating Explained](https://leetify.com/blog/leetify-rating-explained) — วิธีคิด rating
- [Enemy Actually Spotted](https://leetify.com/blog/enemy-actually-spotted/) — วิธีเช็คว่า "เห็นศัตรู"
- Leetify Public API v2 (`/v2/matches/{id}`) — ชื่อ field จริง (ดู `docs/leetify_metrics_reference.md` บน branch `main`)

**สถานะ:** ✅ นิยามชัด ทำตามได้เลย · 🟡 รู้หลักการ แต่ต้อง calibrate ค่าคงที่ · 🔴 ต้องสร้าง model เอง

---

## 0. รากฐาน: "Enemy Spotted" (ทุก metric ด้าน aim ขึ้นกับตัวนี้)

Leetify **ไม่ใช้** radar spotted ของเกม (ช้าได้ถึง 500ms และค้างหลังศัตรูหลบไปแล้ว) แต่ track ตำแหน่งผู้เล่นเอง แล้วตอนเกิด event (ยิง/โดน damage) จะเช็คว่า
- ศัตรูอยู่ใน FOV ไหม
- เห็นส่วนใดของตัว/ปืนศัตรูได้ไหม (line of sight)
- เห็นครั้งแรกเมื่อไหร่ (ใช้คิด TTD และ crosshair placement)

**ทางเลือกของเรา**
| ทาง | ความแม่น | ความยาก |
|---|---|---|
| A. ใช้ `spotted` / `m_bSpottedByMask` จาก demoparser2 | ต่ำ (ปัญหาเดียวกับที่ Leetify เลิกใช้) | ง่าย |
| B. FOV check + raycast กับ collision mesh ของแมพ (เช่น `.tri` จาก vphys, แนวเดียวกับ awpy visibility) | สูง | ต้อง extract geometry ทุกแมพ + raycast ทุก tick ที่สนใจ |

→ **แผน:** เริ่มด้วย A เพื่อให้ pipeline เดินก่อน แล้วสลับเป็น B ทีหลัง โดยออกแบบให้ `visibility` เป็น module ที่ถอดเปลี่ยนได้

> ⚠️ ของเดิมบน `main` คิด preaim เป็นมุมระหว่างเป้ากับ **หัวศัตรู** ซึ่งไม่ใช่นิยามของ Leetify (ดูข้อ 1.4)

---

## 1. Aim

### 1.1 Accuracy (Enemy Spotted) ✅
- **นิยาม:** นัดที่โดน ÷ นัดที่ยิง *ขณะที่เห็นศัตรู*
- **API:** `accuracy_enemy_spotted`, `shots_fired_enemy_spotted`, `shots_hit_enemy_spotted` (มี `accuracy` แบบนับทุกนัดด้วย)
- **ต้องใช้:** `weapon_fire`, `player_hurt` (จับคู่ shot↔hit), visibility ณ tick ที่ยิง
- **คำถามค้าง:** จับคู่นัดยิงกับ hit ยังไงเมื่อเป็นปืนลูกซอง หรือยิงทะลุแล้วโดนหลายคน

### 1.2 Headshot Accuracy ✅
- **นิยาม:** hit ที่โดนหัว ÷ hit ที่โดนศัตรูทั้งหมด **ไม่นับ AWP** (คนละอย่างกับ HS kill %)
- **API:** `accuracy_head`
- **ต้องใช้:** `player_hurt.hitgroup`, `weapon`

### 1.3 Spray Accuracy ✅
- **นิยาม:** เฉพาะ rifle ขณะเห็นศัตรู โดย spray = ยิงต่อเนื่อง **≥ 3 นัด** แล้วคิด hit ใน spray ÷ นัดทั้งหมดใน spray
- **API:** `spray_accuracy`
- **คำถามค้าง:** "ต่อเนื่อง" ตัดที่ช่วงห่างระหว่างนัดเท่าไหร่ (น่าจะใช้ cycle time ของปืน + tolerance), นับนัดแรกของ spray ด้วยไหม (ไฟล์เก่าเขียนว่า "นัด 2–10" ต้องเช็ค)

### 1.4 Crosshair Placement (`preaim`) ✅
- **นิยาม:** มุม (องศา) ระหว่าง eye angles **ตอนเห็นศัตรูครั้งแรก** กับ eye angles **ตอน damage ครั้งแรก** คือวัดว่าต้องลากเมาส์ไปไกลแค่ไหน ยิ่งน้อยยิ่งดี และตัด outlier โดยใช้ median
- **API:** `preaim` (ตัวอย่าง: 4.96°)
- **ต้องใช้:** `pitch`, `yaw` ราย tick, tick ที่เห็นครั้งแรก (ข้อ 0), tick ของ `player_hurt` ครั้งแรกต่อ engagement
- **คำถามค้าง:** นิยามของ "engagement" (เห็นศัตรู → หาย → เห็นใหม่ นับเป็นครั้งใหม่ไหม)

### 1.5 Time to Damage (`reaction_time`) ✅
- **นิยาม:** เวลาจากเห็นศัตรูครั้งแรกถึง damage ครั้งแรก **ตัดค่า ≥ 1 วินาทีทิ้ง** แล้วใช้ median ซึ่งไม่ใช่ reaction time จริง
- **API:** `reaction_time` (หน่วยวินาที เช่น 0.586)
- **ต้องใช้:** ข้อมูลชุดเดียวกับ 1.4 (ใช้ engagement เดียวกัน)

### 1.6 Counter-Strafing ✅
- **นิยาม:** นับเฉพาะนัด rifle ที่ยิงใส่ศัตรูที่เห็นอยู่ **ไม่นับนัดที่ยิงตอนนั่ง** นัด "good" คือความเร็วตอนยิง < **34% ของ max speed ของปืนนั้น**
- **API:** `counter_strafing_shots_all/good/bad`, `counter_strafing_shots_good_ratio`
- **ต้องใช้:** `velocity_X/Y` (ใช้ความเร็วแนวราบ), `ducking`, weapon ณ tick ที่ยิง, ตาราง max speed ของปืน
- **max speed (ต้องเช็คกับ `items_game` อีกที):** AK-47 215 · M4A4/M4A1-S 225 · FAMAS 220 · Galil 215 · AUG 220 · SG 553 210 · AWP 200 · SSG 08 230
- **คำถามค้าง:** "rifle" รวม sniper ไหม, คิดความเร็วตอน scope ของ AWP/AUG/SG ยังไง

---

## 2. Utility

| Metric | นิยาม Leetify | สถานะ |
|---|---|---|
| Enemies Flashed / Flash | ศัตรูที่ตาบอด **> 1.1s** ÷ flash ที่โยน (สูงสุด 5). **ไม่นับคนที่ตายไปแล้ว** (`player_blind` ยังยิงให้ศพ) และไม่ตัด duration ตอนเหยื่อตาย | ✅ verified |
| Teammates Flashed / Flash | เหมือนกัน แต่นับเพื่อน **รวมตัวเองด้วย** | ✅ verified |
| Flash Blind Duration | ต่อ flash เอาค่าตาบอด **นานสุด** ของศัตรูที่ยังมีชีวิต แล้วเฉลี่ยทุก flash ที่โดนศัตรู ≥ 1 คน **กี่วินาทีก็ได้ (ไม่มีเกณฑ์ 1.1s ตรงนี้)**. ไม่มี flash โดนเลย = Leetify แสดง 0 | ✅ verified |
| Flash Assist % | kill ที่ศัตรูยังตาบอดจาก flash เรา (โดยใครก็ได้ในทีม **รวมตัวเอง**) นับ **ต่อ kill** (flash ลูกเดียวได้หลาย kill) ÷ flash ที่โยน. ไม่ใช่ `assistedflash` ของเกม | ✅ verified |
| Flashbangs Leading to Kills | ตัวเศษของ Flash Assist % ข้างบน | ✅ verified (ผ่าน Flash Assist %) |
| HE Damage / HE | damage HE ใส่ศัตรูรวม ÷ HE ที่โยน | ✅ verified |
| HE Team Damage / HE | damage HE ใส่เพื่อน **รวมตัวเอง** ÷ HE ที่โยน | ✅ verified |
| Unused Utility on Death | มูลค่า $ ของระเบิดที่ถือตอนตาย เฉลี่ยต่อการตาย. ระเบิดที่**เพิ่งปา** (≤ 1s ก่อนตาย ยังเป็น active weapon) ไม่นับ. ตัวหาร**รวม death หลังจบแมตช์**ด้วย (มูลค่า 0) | ✅ verified |
| [CT] Smokes That Stopped a Push | smoke ฝั่ง CT ที่มีศัตรูอยู่ใน **800 units** จากจุดที่ควันบาน ÷ smoke CT ทั้งหมด | 🟡 ไม่รู้ว่าวัดช่วงเวลาไหนหลังควันบาน |

**ต้องใช้:** `player_blind` (`blind_duration`, `attacker`), `flashbang_detonate`, `hegrenade_detonate`, `smokegrenade_detonate`, `player_hurt` (weapon=hegrenade), `player_death` + inventory ตอนตาย, ราคาระเบิด
- ~~คำถามค้าง: "kill ระหว่างตาบอด"~~ ใช้ `blind_tick ≤ kill_tick ≤ blind_tick + duration` แล้วตรง (ทุกเคสใน inferno-44a522c3 เป็น blind > 1.1s จึงยังไม่รู้ว่า Leetify ใช้เกณฑ์ 1.1s ตรงนี้ด้วยไหม)

---

## 3. Trades 🟡

- **Trade Kills:** opportunities / attempts / succeeded หมายถึงตอนเพื่อนตาย เรามีโอกาส trade ไหม ได้พยายามไหม และสำเร็จไหม
- **Traded Deaths:** ฝั่งกลับกัน คือตอนเราตาย เพื่อนมีโอกาส trade ให้ไหม และสำเร็จไหม
- **Glossary ไม่ได้ให้ตัวเลข** ต้องหาเองว่า:
  - trade window กี่วินาที: จาก KAST ของ inferno-44a522c3 ได้ **[2.05, 4.84) s** (trade ที่ 2.05s ต้องนับ, ที่ 4.84s ต้องไม่นับ). ตอนนี้ใช้ 4.0s. ที่ 4.0s นับแบบง่าย (คนฆ่าเราถูกเพื่อนเราฆ่าภายใน window) ได้ traded deaths succeeded และ trade kills succeeded ตรงครบ 10 คน แต่ยังไม่ได้ calibrate
  - "opportunity" คืออะไร: ยังมีชีวิต + อยู่ใกล้ในระยะ X หรือ + เห็นคนฆ่า
  - "attempt" คืออะไร: ยิง/ทำ damage ใส่คนฆ่าภายใน window หรือแค่วิ่งเข้าหา
- **วิธีหา:** calibrate กับค่าจาก Leetify API ของแมตช์ที่เรามีทั้ง `.dem` และหน้า Leetify (ดูข้อ 6)

---

## 4. General ✅

kills, deaths, assists, HS kills, K/D, damage, ADR (`dpr`), KAST, rounds survived, multi-kills 1k–5k, rounds won/lost, MVP, score
- ตรงไปตรงมา แต่ระวัง: ต้องตัด warmup/knife round, ต้องจัดการ damage ที่เกิน HP ที่เหลือ (ADR ส่วนใหญ่ cap ที่ HP ที่เหลือ), team damage และ suicide
- KAST ต้องใช้ trade window เดียวกับข้อ 3
- **สิ่งที่ยืนยันแล้ว (inferno-44a522c3, ตรงครบ 10 คน):**
  - **Damage** = HP ที่หายจริง: `min(dmg_health, HP ที่เหลือ)` และ**นัดที่ฆ่า = HP ที่เหลือทั้งหมด** (`dmg_health` อาจน้อยกว่า HP ที่หายจริง 1 เพราะ damage เป็นเศษ). ไม่รวม team damage
  - **Deaths** นับทุกการตายรวมโดน teamkill. **ไม่นับ** death หลังจบแมตช์ (หลัง `cs_win_panel_match` เช่น world suicide ตอนขึ้น scoreboard)
  - **Assists** คิดจาก `assister` ของทุก death **รวม teamkill** (เช่นเราทำ damage ใส่ศัตรูแล้วเพื่อนเขา teamkill = assist ของเรา) ถ้าผู้ assist อยู่คนละทีมกับเหยื่อ. **ไม่นับ** flash assist (`assistedflash`) และการ assist ให้ศัตรูฆ่าเพื่อนตัวเอง
  - **Opening duel** = kill แรกของรอบที่ไม่ใช่ teamkill/suicide: ตรงครบ 13 รอบ, attempt % / success % ตรง
  - Leetify General ไม่มีคอลัมน์ 1K

---

## 5. Leetify Rating 🔴

**หลักการ (จากบทความ)**
- คิด rating รายรอบแล้วเฉลี่ยทั้งแมตช์ โดยเป็นระบบ zero-sum คือผลรวมทั้งแมตช์เป็น 0
- พื้นฐานคือ **round win probability (WP)** ที่เปลี่ยนไปหลังแต่ละ kill
- **WP เริ่มต้น:** จัดเศรษฐกิจของแต่ละทีมเป็น 4 tier (ตาราง CT กับ T ต่างกัน) แล้ว lookup จากข้อมูล HLTV
- **WP ระหว่างรอบ:** ขึ้นกับ economy tier, จำนวนคนที่ยังเหลือ และฝั่งที่ได้ kill ล่าสุด
- **แบ่ง credit ของ kill:** killer 35% · คนทำ damage ใส่เหยื่อ 30% · flash assist 15% · คนที่ตายแล้วถูก trade 20% (ถ้าไม่มีบทบาทไหน ส่วนที่เหลือขยายตามสัดส่วน) ส่วนโทษของการตายตกที่เหยื่อคนเดียว
- **เพิ่มเติม:** save ปืนได้ rating ตาม WP รอบหน้าที่เพิ่มขึ้น, ชนะ/แพ้ด้วย objective ได้/เสีย rating, ถ้ารอบจบโดยที่ทั้งสองฝั่งยังมีคนรอด จะแบ่ง rating เท่าๆ กันในกลุ่มคนรอด
- **ระดับ:** Great > +5.12 · Good +2.09…+5.12 · Average ±2.09 · Subpar −5.12…−2.09 · Poor < −5.12

**สิ่งที่ Leetify ไม่บอก (ต้องสร้างเอง):** ค่าในตาราง WP, เกณฑ์เงินของแต่ละ tier, ค่าคงที่แปลง ΔWP เป็นคะแนน, ผลของ bomb plant และเวลาต่อ WP

→ **แผน:** ทำ WP model ของเราเอง ("Impact Rating") ด้วยการ fit จาก demo จำนวนมาก (pro demos จาก HLTV + demo ของ user) ใช้กติกาแบ่ง credit ตามข้างบน **ไม่ต้องพยายามให้ตรงกับ Leetify เป๊ะ** แค่ให้ correlation สูงพอ

---

## 6. วิธี validate

1. หาแมตช์ที่มีทั้ง `.dem` และข้อมูลบน Leetify. คู่ที่ใช้อยู่: `scripts/demos/003852158461294936246_0991785667.dem.bz2` ↔ `data/validation/inferno-44a522c3.json` (Inferno 13:0). **`dust2-f2633f5c.json` ยังไม่มี demo ที่ตรง** (`dust2win.dem` เป็นคนละแมตช์)
   - ก่อน validate ให้เช็ค map + จำนวนรอบ + ชื่อผู้เล่นว่าตรงกันก่อน (`validate` ทำให้เองและหยุดถ้าไม่ตรง)
2. ดึงค่าจาก Leetify API แล้วเทียบกับที่เราคำนวณ ราย player ราย metric
3. ใช้ตอน dev เท่านั้น: [developer guidelines](https://leetify.com/blog/leetify-api-developer-guidelines) **ห้ามเก็บข้อมูลจาก API ไว้** และถ้าจะแสดงข้อมูล Leetify บนเว็บต้องใส่ attribution "Data Provided by Leetify" และห้ามเอาชื่อ Leetify มาใช้ในชื่อแอป
4. เป้าหมาย: ✅ ต่างไม่เกิน ~2–3%, 🟡 calibrate จนใกล้เคียง, 🔴 ดูแค่ correlation

## 7. ลำดับที่จะทำ
1. General + Utility (✅ ส่วนใหญ่ แค่ใช้ event ไม่ต้องมี visibility)
2. Visibility module (ทาง A ก่อน)
3. Aim ทั้งหมด (1.1–1.6)
4. Trades (calibrate) → KAST
5. WP model → Impact Rating
