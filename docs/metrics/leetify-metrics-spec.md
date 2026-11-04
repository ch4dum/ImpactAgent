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
สถานะต่อกฎย่อยดูที่ **§8** (✅ = มีเคสพิสูจน์ใน 2 แมตช์ / 🟢 = มีเคสพิสูจน์ 1 แมตช์ อีกแมตช์ไม่ขัด / 🟡 = สมมติฐาน ยังไม่มีเคสแยก)

| Metric | นิยาม Leetify | สถานะ |
|---|---|---|
| Enemies Flashed / Flash | ศัตรูที่ตาบอด **> 1.1s** ÷ flash ที่โยน (สูงสุด 5). **ไม่นับคนที่ตายไปแล้ว** (`player_blind` ยังยิงให้ศพ) และไม่ตัด duration ตอนเหยื่อตาย | ✅ |
| Teammates Flashed / Flash | เหมือนกัน แต่นับเพื่อน **รวมตัวเองด้วย** | ✅ |
| Flash Blind Duration | ต่อ flash เอาค่าตาบอด **นานสุด** ของศัตรูที่ยังมีชีวิต แล้วเฉลี่ยทุก flash ที่โดนศัตรู ≥ 1 คน **กี่วินาทีก็ได้ (ไม่มีเกณฑ์ 1.1s ตรงนี้)**. ไม่มี flash โดนเลย = Leetify แสดง 0 | ✅ |
| Flash Assist % | kill ที่ศัตรูยังตาบอดจาก flash เรา (โดยใครก็ได้ในทีม **รวมตัวเอง**) นับ **ต่อ kill** (flash ลูกเดียวได้หลาย kill) ÷ flash ที่โยน. ไม่ใช่ `assistedflash` ของเกม | ✅ |
| Flashbangs Leading to Kills | ตัวเศษของ Flash Assist % ข้างบน | ✅ (ผ่าน Flash Assist %) |
| HE Damage / HE | damage HE ใส่ศัตรูรวม **แบบดิบ (`dmg_health` ไม่ cap ที่ HP ที่เหลือ)** ÷ HE ที่โยน | 🟢 |
| HE Team Damage / HE | damage HE ใส่เพื่อน **รวมตัวเอง** ÷ HE ที่โยน (ดิบหรือ cap ยังไม่รู้ ใช้ดิบ) | 🟢 / 🟡 |
| Unused Utility on Death | มูลค่า $ ของระเบิดที่ถือตอนตาย เฉลี่ยต่อการตาย. **ระเบิดชนิดเดียวกันนับครั้งเดียว** (flash 2 ลูก = $200). ระเบิดที่**เพิ่งปา** (≤ 1s ก่อนตาย ยังเป็น active weapon) ไม่นับ. ตัวหาร**รวม death หลังจบแมตช์**ด้วย (มูลค่า 0) | ✅ / 🟢 |
| [CT] Smokes That Stopped a Push | smoke ฝั่ง CT ที่มีศัตรูอยู่ใน **800 units** จากจุดที่ควันบาน ÷ smoke CT ทั้งหมด | 🟡 ไม่รู้ว่าวัดช่วงเวลาไหนหลังควันบาน |

**ต้องใช้:** `player_blind` (`blind_duration`, `attacker`), `flashbang_detonate`, `hegrenade_detonate`, `smokegrenade_detonate`, `player_hurt` (weapon=hegrenade), `player_death` + inventory ตอนตาย, ราคาระเบิด
- ~~คำถามค้าง: "kill ระหว่างตาบอด"~~ ใช้ `blind_tick ≤ kill_tick ≤ blind_tick + duration` แล้วตรง (ทุกเคสใน 2 แมตช์เป็น blind > 1.1s จึงยังไม่รู้ว่า Leetify ใช้เกณฑ์ 1.1s ตรงนี้ด้วยไหม)

---

## 3. Trades 🟡 (succeeded ✅, opportunity / attempt 🟡)

- **Trade Kills:** opportunities / attempts / succeeded ตอนเพื่อนตาย เรามีโอกาส trade ไหม ได้พยายามไหม และสำเร็จไหม (นับต่อคู่ death × เพื่อนที่ยังรอด)
- **Traded Deaths:** ฝั่งกลับกัน ตอนเราตาย มีเพื่อน ≥ 1 คนที่มีโอกาส / พยายาม / สำเร็จไหม (นับต่อ death)
- ข้อมูลอยู่ในตาราง `trade_windows` (1 แถวต่อ death × เพื่อนของคนตายที่ยังรอด ณ tick ที่ตาย; ไม่นับ teamkill / suicide / post-match). feature ดึงจาก tick ใน window ทุก 4 tick แล้วทิ้ง tick data
- **Trade window:** ใช้ KAST + traded deaths succeeded + trade kills succeeded ของ 2 แมตช์ (20 คน) ได้ **[3.48, 4.47) s** (trade ที่ห่าง 3.484s ต้องนับ, ที่ 4.469s ต้องไม่นับ). ใช้ 4.0s ✅ ช่วง
- **Succeeded** = เพื่อนฆ่าคนฆ่าภายใน window ✅ (20/20 ทั้ง 2 แมตช์ ทั้ง TK และ TD)
- **Opportunity / Attempt (🟡 สมมติฐาน ยังไม่ตรง):** grid search window {3.5, 4, 5, 6}s × นิยามหลายแบบ (ตัวเลข = ผู้เล่นที่ตรงเป๊ะ จาก 20)

  | นิยามที่ลอง | TK opp | TD opp | TK att | TD att |
  |---|---|---|---|---|
  | opp = เพื่อนที่ยังรอดทุกคน | 0–3 | 2–5 | | |
  | opp = ระยะจากคนตาย / คนฆ่า < 500…2000u | ≤ 5 | ≤ 5 | | |
  | opp = เพื่อนเห็นคนฆ่า (`approximate_spotted_by`) | 5 | 5 | | |
  | opp = เพื่อนเห็นคนฆ่า **หรือ** คนฆ่าเห็นเพื่อน | 7 | 6 | | |
  | **opp = attempt หรือ เห็นกันทางใดทางหนึ่ง** (ใช้อยู่) | **12** | **9** | | |
  | att = ทำ damage ใส่คนฆ่า | | | 4 | 4 |
  | att = ยิงอะไรก็ได้ใน window | | | 5–10 | 8 |
  | **att = damage ใส่คนฆ่า หรือ ยิงตอนเห็นคนฆ่าและเป้าห่าง < 20°** (ใช้อยู่, 4s) | | | **12** | **13** |

  ตอนนี้ได้ inferno 22/40, mirage 25/40 (metric × ผู้เล่น) ห่างเฉลี่ย 4–48%. **สาเหตุที่น่าจะเป็น:** `approximate_spotted_by` ของเกมเป็นค่าประมาณ Leetify น่าจะใช้ visibility ของตัวเอง → รอ visibility module (roadmap Phase 1) แล้ว calibrate ใหม่. validate รายงานกลุ่มนี้เป็น `calibrating` ไม่ gate
- **Opening traded %** = opening death ที่ถูก trade (succeeded) ÷ opening death ✅ (20/20)

---

## 4. General ✅

kills, deaths, assists, HS kills, K/D, damage, ADR (`dpr`), KAST, rounds survived, multi-kills 1k–5k, rounds won/lost, MVP, score
- ตรงไปตรงมา แต่ระวัง: ต้องตัด warmup/knife round, ต้องจัดการ damage ที่เกิน HP ที่เหลือ (ADR ส่วนใหญ่ cap ที่ HP ที่เหลือ), team damage และ suicide
- KAST ต้องใช้ trade window เดียวกับข้อ 3
- **สิ่งที่เจอ (รายละเอียดสถานะใน §8):**
  - **Damage** = HP ที่หายจริง: `min(dmg_health, HP ที่เหลือ)` และ**ทุก hit ใน tick ที่ฆ่ารวมกัน = HP ที่เหลือก่อน tick นั้น** (นัดเดียวหรือลูกซองหลาย pellet; `dmg_health` อาจน้อยกว่า HP ที่หายจริง 1 เพราะ damage เป็นเศษ). ไม่รวม team damage
  - **Deaths** นับทุกการตายรวมโดน teamkill. **ไม่นับ** death หลังจบแมตช์ (หลัง `cs_win_panel_match` เช่น world suicide ตอนขึ้น scoreboard)
  - **Assists** คิดจาก `assister` ของทุก death **รวม teamkill** (เช่นเราทำ damage ใส่ศัตรูแล้วเพื่อนเขา teamkill = assist ของเรา) ถ้าผู้ assist อยู่คนละทีมกับเหยื่อ. **ไม่นับ** flash assist (`assistedflash`) และการ assist ให้ศัตรูฆ่าเพื่อนตัวเอง
  - **KAST:** "A" = damage assist **หรือ flash assist** (ต่างจากคอลัมน์ Assists). T = trade window ข้อ 3. ตัวหาร = รอบที่ผู้เล่นเล่น
  - **ADR / KAST / HLTV** หารด้วยรอบที่ผู้เล่นเล่น แต่ **Opening attempt %** หารด้วยรอบทั้งแมตช์
  - **Opening duel** = kill แรกของรอบที่ไม่ใช่ teamkill/suicide: ตรงครบทุกรอบ (inferno 13/13), attempt % / success % ตรง
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

1. หาแมตช์ที่มีทั้ง `.dem` และข้อมูลบน Leetify. คู่ที่ใช้อยู่ (`python -m impactagent validate-all` รันทุกคู่):
   - `inferno-44a522c3.json` ↔ `scripts/demos/003852158461294936246_0991785667.dem.bz2` (Inferno 13:0) ใช้ calibrate
   - `mirage-65db631a.json` ↔ `scripts/demos/003850878442929127864_1489073941.dem.bz2` (Mirage 13:11) **holdout**: ก่อนแก้โค้ดได้ 274/290
   - **`dust2-f2633f5c.json` ไม่มี demo ที่ตรง** (`dust2win.dem` เป็นคนละแมตช์) `validate-all` จะ SKIP
   - ก่อน validate ให้เช็ค map + จำนวนรอบ + ชื่อผู้เล่นว่าตรงกันก่อน (`validate` ทำให้เองและหยุดถ้าไม่ตรง). ชื่อใน demo ต่างจาก Leetify ได้ ใส่ `"aliases": [...]` ใน truth
2. ดึงค่าจาก Leetify API แล้วเทียบกับที่เราคำนวณ ราย player ราย metric
3. ใช้ตอน dev เท่านั้น: [developer guidelines](https://leetify.com/blog/leetify-api-developer-guidelines) **ห้ามเก็บข้อมูลจาก API ไว้** และถ้าจะแสดงข้อมูล Leetify บนเว็บต้องใส่ attribution "Data Provided by Leetify" และห้ามเอาชื่อ Leetify มาใช้ในชื่อแอป
4. เป้าหมาย: ✅ ต่างไม่เกิน ~2–3%, 🟡 calibrate จนใกล้เคียง, 🔴 ดูแค่ correlation

## 7. ลำดับที่จะทำ
1. General + Utility (✅ ส่วนใหญ่ แค่ใช้ event ไม่ต้องมี visibility)
2. Visibility module (ทาง A ก่อน)
3. Aim ทั้งหมด (1.1–1.6)
4. Trades (calibrate) → KAST
5. WP model → Impact Rating

## 8. สถานะกฎ (validate 2 แมตช์: core inferno 275/275, mirage 320/320; opening 13/13, 24/24; clutch 14/15, 28/28)

✅ = มีเคสพิสูจน์ใน 2 แมตช์ · 🟢 = มีเคสพิสูจน์ 1 แมตช์ อีกแมตช์ไม่ขัด · 🟡 = สมมติฐาน (ยังไม่มีเคสที่แยกทางเลือกได้)

| กฎ | หลักฐาน | สถานะ |
|---|---|---|
| Damage = `min(dmg_health, HP เหลือ)`, tick ที่ฆ่ารวม = HP เหลือก่อน tick | inferno: kill นัดเดียว +1 (2 คน); mirage: ลูกซองหลาย pellet (3 คน, +1…+5) | ✅ |
| Deaths ไม่นับ death หลัง `cs_win_panel_match` | inferno 2 เคส, mirage 1 เคส (ch4dum) | ✅ |
| Assists: รวม teamkill ถ้าผู้ assist เป็นศัตรูของเหยื่อ; ไม่นับ flash assist; ไม่นับช่วยศัตรูฆ่าเพื่อน | inferno หลายเคส; mirage holdout ตรง 10/10 โดยไม่แก้ | ✅ |
| KAST "A" รวม flash assist | mirage: Boonrywaa r10 | 🟢 |
| Trade window ∈ [3.48, 4.47) s (ใช้ 4.0) | KAST + traded deaths + trade kills succeeded ของ 20 คน | ✅ ช่วง / 🟡 ค่าเป๊ะ |
| Opening attempt % หารด้วยรอบทั้งแมตช์ | mirage: J เล่น 22/24 รอบ | 🟢 |
| Blind ใส่คนที่ตายแล้วไม่นับ | inferno: yyh → Zeus r11 | 🟢 |
| Blind duration = เฉลี่ย max ต่อ flash ที่โดนศัตรูกี่วิก็ได้ | inferno 3 คน + mirage 10/10 holdout | ✅ |
| Flash Assist % นับต่อ kill รวมตัวเอง ÷ flash ที่โยน | inferno (Wagga flash ลูกเดียว 3 kill) + mirage 10/10 holdout | ✅ |
| Flash Assist % ต้อง blind > 1.1s ไหม | ไม่มีเคส kill ระหว่าง blind ≤ 1.1s | 🟡 |
| HE ใส่ศัตรูใช้ `dmg_health` ดิบ (ไม่ cap) | mirage: o2donggg, V | 🟢 |
| HE team รวมตัวเอง | inferno: 3 คน | 🟢 |
| HE team ดิบหรือ cap | ไม่มีเคสที่ต่างกัน | 🟡 (ใช้ดิบ) |
| Molotov damage ดิบหรือ cap | ไม่มีเคสที่ต่างกัน | 🟡 (ใช้ cap) |
| Unused: ระเบิดชนิดเดียวกันนับครั้งเดียว | mirage 5 คน (11 การตาย) | 🟢 |
| Unused: ไม่นับระเบิดที่เพิ่งปา (≤ 1s และยังเป็น active weapon) | inferno: Donkie HE; mirage: B ตายโดยถือ flash เป็น active แต่ไม่ได้ปา = นับ | ✅ |
| Unused: ตัวหารรวม death หลังจบแมตช์ | inferno: Wagga, yyh; mirage: ch4dum | ✅ |
| Unused: ราคา (incendiary 500, decoy 50) | incendiary 22 การตาย, decoy 3 การตาย | ✅ |
| Grace 1s ของ "เพิ่งปา" | เคสเดียว ห่าง 0.48s | 🟡 ค่าเป๊ะ |
| Trade succeeded = เพื่อนฆ่าคนฆ่าใน window (TK ต่อเพื่อน, TD ต่อ death) | 40/40 player × metric | ✅ |
| Trade opportunity / attempt (§3) | ดีสุด ~60% ตรงเป๊ะ | 🟡 รอ visibility |
| Opening traded % = opening death ที่ถูก trade ÷ opening death | 20/20 | ✅ |
| Opening duel = kill แรกของรอบ (ไม่นับ TK / suicide) | 37/37 รอบ | ✅ |
| Clutch เริ่มเมื่อ death ทำให้เหลือคนเดียวในฝั่ง และศัตรูเหลือ ≥ 1; vs = ศัตรูที่เหลือ; นับทุก death (TK / suicide / world) ยกเว้น post-match | 42/43 | ✅ |
| Clutch kills = kill ศัตรูหลังเริ่ม clutch จนจบรอบ | 42/43 | ✅ |
| Clutch outcome: won = ฝั่งชนะ, lost = ตายในรอบ, saved = แพ้แต่รอด | 42/43 | ✅ |
| เคสที่อธิบายไม่ได้: inferno r13 Suzy (Leetify vs5 k1 saved, เรา vs5 k0 lost) ตายด้วย `world` ตรง tick จบรอบ และ kill เดียวของเธอเป็น teamkill **ก่อน**เริ่ม clutch. "suicide ไม่นับเป็นตาย" แก้ outcome ได้แต่ kills ยังไม่ตรง; "นับ kill ทั้งรอบรวม TK" ทำให้ 17 เคสอื่นพัง | 1 เคส | 🟡 ไม่ฝืนแก้ (clutch ไม่ gate) |
