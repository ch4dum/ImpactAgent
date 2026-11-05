# Leetify Metrics Spec (Phase 0)

แกะ metric ของ Leetify ทีละตัว: Leetify นิยามว่าอะไร → ต้องดึงอะไรจาก `.dem` → เราจะคำนวณยังไง → อะไรที่ยังไม่รู้

**แหล่งข้อมูล**
- [Leetify Stats Glossary](https://leetify.com/blog/leetify-stats-glossary) — นิยามทางการ
- [Leetify Rating Explained](https://leetify.com/blog/leetify-rating-explained) — วิธีคิด rating
- [Enemy Actually Spotted](https://leetify.com/blog/enemy-actually-spotted/) — วิธีเช็คว่า "เห็นศัตรู"
- Leetify Public API v2 (`/v2/matches/{id}`) — ชื่อ field จริง (ดู `docs/leetify_metrics_reference.md` บน branch `v1-draft`)

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

→ **ทำแล้ว (2026-11-05):** `impactagent/visibility/` มีทั้ง A (`spotted`) และ B (`raycast`: awpy-data mesh + lag window + ควัน + FOV) สลับได้ ใช้ B เป็นค่าหลัก. ผลกับ kill (`python -m impactagent visibility`):

  | backend | kill ปกติ inferno / mirage | ผ่านควัน | wallbang |
  |---|---|---|---|
  | `spotted` ของเกม | 75.0% / 74.3% | 0/7, 1/7 | 2/2, 2/8 |
  | raycast LOS (tick เดียว) | 95.8% / 95.4% | 7/7, 5/7 | 1/2, 1/8 |
  | + lag window 7 tick | 100% / 99.3% | 7/7, 7/7 | 1/2, 2/8 |
  | + ควัน + FOV 50° (ค่าหลัก) | 100% / 98.7% | 0/7, 2/7 | 1/2, 2/8 |

> ⚠️ ของเดิมบน `v1-draft` คิด preaim เป็นมุมระหว่างเป้ากับ **หัวศัตรู** ซึ่งไม่ใช่นิยามของ Leetify (ดูข้อ 1.4)

---

## 1. Aim

**ผลการ implement (2026-11-05, `impactagent/parse/aim.py` + `impactagent/metrics/aim.py`, visibility = raycast):** dev บน Inferno แล้ว holdout บน Mirage (ก่อนแก้โค้ด core aim ได้ 9/20)

| metric (id) | นิยามที่ใช้ | inferno | mirage | สถานะ |
|---|---|---|---|---|
| `shots_fired` | ปืนทุกนัดในช่วงรอบ (รวมหลัง round_end) **ไม่นับลูกซอง** และ**ไม่นับนัดใน tick ที่คนยิงตาย**, ไม่นับมีด / taser / ระเบิด | 10/10 | 10/10 | exact |
| `accuracy_all` | นัดที่ทำ damage ศัตรูใน tick เดียวกัน ÷ shots_fired (ลูกซอง / ทะลุ 2 คน = 1 hit) | 10/10 | 10/10 | exact |
| `accuracy_head` | ต่อนัด ไม่นับ AWP / ลูกซอง: นัดที่ hurt **ทุกครั้ง**เป็นหัว ÷ นัดที่โดน | 10/10 | 10/10 | exact |
| `accuracy_enemy_spotted` | นัดที่ยิงตอนเห็นศัตรู ≥ 1 คน (raycast + ควัน + FOV) | 3/10 | 6/10 | calibrating (MAE 0.025 / 0.012) |
| `counter_strafe_pct` | rifle (ไม่นับ sniper) ยิงตอนเห็นศัตรู ไม่นั่ง, ดี = speed < 34% ของ max | 2/9 | 3/9 | calibrating |
| `spray_accuracy` | rifle spray ≥ 3 นัด (gap ≤ 0.25s) นัดที่ 3 เป็นต้นไป ตอนเห็นศัตรู | 0/7 | 3/8 | calibrating |
| `first_bullet_accuracy` | นัดแรกหลังไม่ยิง ≥ 0.5s ตอนเห็นศัตรู ไม่นับ sniper | 1/10 | 0/10 | calibrating |
| `ttd_ms` | median (first damage − first seen) < 1s | 0/10 | 0/10 | calibrating |
| `ttk_ms` | median (kill − first seen) | 1/10 | 0/10 | calibrating |
| `crosshair_placement_deg` | median มุม view ตอน first seen กับตอน first damage, ttd < 1s | 0/10 | 0/10 | calibrating |

- **TTD / TTK / crosshair ของเราต่ำกว่า Leetify ทุกคน** (TTD สั้นกว่า 16–390ms, crosshair เล็กกว่า ~2 เท่า) ทุก config ที่ลอง (gap 0–64 tick, FOV / ไม่มี FOV, ควัน / ไม่มีควัน, ตัด TTD สั้น, mean แทน median) จึงน่าจะมาจาก **first seen ของเราช้ากว่า** ไม่ใช่สูตร. สงสัย: mesh ของ awpy (physics) มี player clip / prop ที่ไม่บังสายตาจริง หรือ Leetify ใช้ hitbox ที่ใหญ่กว่า 3 จุดของเรา (ลองเพิ่มจุด ±8–16u แล้วไม่ดีขึ้นใน spotted accuracy)
- **Spray accuracy ของ Leetify ไม่น่าใช่ hit ÷ นัด**: inferno yyh 0.83 ทั้งที่ accuracy รวม 0.11 และ spotted 0.51 ลองแบบ "spray ที่โดน ≥ k ครั้ง" แล้วก็ไม่ตรง อาจวัด recoil control จากมุม (ต้องใช้ aim punch)
- **ทดลอง first_seen (ไม่ได้เปลี่ยนค่าหลัก):** TTD bias (ms) Inferno / Mirage: raycast 3 จุด (ใช้อยู่) −173 / −143 · `spotted` −338 / −337 · union raycast ∪ spotted −163 / −141 · **raycast 8 จุด** (หัว คอ อก เอว เข่า เท้า + ไหล่ซ้ายขวา ±14u) **−125 / −83** · union 8 จุด ∪ spotted −114 / −78. Crosshair bias −5.7 / −4.6 → −4.9 / −4.3 (แทบไม่เปลี่ยน) → TTD ห่างเพราะ hitbox ของเราเล็กไป (เพิ่มจุดแล้วเห็นเร็วขึ้น), ส่วน crosshair น่าจะเป็นที่นิยาม (ไม่ใช่ first_seen อย่างเดียว). `spotted` ของเกมช้ากว่า raycast มาก
- Null: spray null เมื่อไม่มี spray ที่เข้าเกณฑ์; Leetify ให้ null ใน 3 กรณีที่เราได้ค่า (spray 2–4 นัด) → เกณฑ์ spray ของ Leetify เข้มกว่า

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
- **ลองใหม่ด้วย visibility module (2026-11-05, ไม่ได้เปลี่ยนโค้ด):** sample ทุก 2 tick ใน window 2–5s, เพื่อนเห็นคนฆ่า (raycast / raycast ไม่มี FOV / `spotted` / union), คนฆ่าเห็นเพื่อน, มุมเป้า, ระยะ (ถึงคนฆ่า / คนตาย 300–2000u), attempt = ยิงหรือทำ damage **ขณะเห็นคนฆ่า**. Dev บน Inferno แล้วล็อก candidate ไว้ก่อน holdout:

  | candidate (window 4s) | inferno (dev) | mirage (holdout) |
  |---|---|---|
  | raycast: att = ยิง/damage ขณะเห็น, opp = เห็น \| att | 23/40 | **11/40** |
  | `spotted` ทุก 2 tick: opp = เห็น \| คนฆ่าเห็น \| att | 26/40 | **2/40** |
  | union raycast ∪ spotted | 23/40 | 11/40 |
  | **นิยามเดิม** (`approximate_spotted_by` ทุก 4 tick, att = damage \| ยิงขณะเห็น < 20°) | 22/40 | **25/40** |

  ดีสุดบน Inferno เมื่อดูทีละ metric: TK opp 7/10, TD opp 6/10, TK att 9/10, TD att 7/10 แต่ไม่ generalize. Mirage: candidate นับ attempt **ขาด** (raycast −10 / −10, spotted −29 / −26 จาก truth 64 / 57) ส่วน opportunity เกิน (+16 / +7). Leetify ให้ attempt ÷ opportunity = 0.59 บน Inferno แต่ 0.90 บน Mirage จึงน่าจะนับ attempt กว้างกว่า "ยิงขณะเห็น" (เช่น ยิงอะไรก็ได้ หรือมี reposition / utility) และ opportunity ไม่ใช่แค่ "เห็นคนฆ่า". เคสที่ใช้แยก: inferno Wagga r8 ทำ damage ใส่คนฆ่าที่ 2.0s ก่อนเห็น (3.97s) แต่ Leetify ให้ TK attempt = 0. **คงนิยามเดิม + `calibrating`**; ต้องมี truth ราย death (ไม่ใช่แค่ยอดต่อ player) จึงจะแยกได้
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

## 8. สถานะกฎ (validate 2 แมตช์: core inferno 305/305, mirage 350/350; opening 13/13, 24/24; clutch 15/15, 28/28)

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
| Trade opportunity / attempt (§3) | นิยามเดิม 22/40, 25/40; นิยามใหม่ที่ใช้ raycast ได้ 23/40 บน Inferno แต่ holdout Mirage แค่ 11/40 | 🟡 คงนิยามเดิม (visibility อย่างเดียวไม่พอ) |
| Opening traded % = opening death ที่ถูก trade ÷ opening death | 20/20 | ✅ |
| Opening duel = kill แรกของรอบ (ไม่นับ TK / suicide) | 37/37 รอบ | ✅ |
| Clutch เริ่มเมื่อ death ทำให้เหลือคนเดียวในฝั่ง และศัตรูเหลือ ≥ 1; vs = ศัตรูที่เหลือ; นับทุก death (TK / suicide / world / ออกเกม) ยกเว้น post-match | 43/43 | ✅ |
| Clutch kills = kill ศัตรูหลังเริ่ม clutch จนจบรอบ **+ death แบบ world/suicide ของศัตรู (เช่นออกเกม) ที่เราเป็น assister** นับรวม post-match | 43/43; ส่วน "+ assister" มีหลักฐาน 1 เคส (inferno r13: Wagga ออกเกมหลังจบแมตช์ assister = Suzy) | ✅ / 🟢 |
| Clutch outcome: won = ฝั่งชนะ, lost = ตายในรอบ, saved = แพ้แต่รอด. **ตายเพราะออกเกม (`by_disconnect`) ไม่นับว่าตาย** | 43/43; ส่วน "ออกเกม" มีหลักฐาน 1 เคส (inferno r13 Suzy) | ✅ / 🟢 |
| Visibility: ตา = Z + 64 + `m_flDuckViewOffset` | demo ไม่มี `m_vecViewOffset`; kill ปกติเห็น 72/72, 150/152 | ✅ |
| Visibility: lag window คงที่ 7 tick (ไม่ใช้ ping) | rewind ที่ต้องใช้ไม่สัมพันธ์กับ `ping` ของคนยิง (rank corr 0.01, 64 hit 2 แมตช์); kill ปกติต้องย้อนสูงสุด 6 tick | ✅ |
| Visibility: ควัน = ทรงกลม R 144 / +32z / บล็อกหลังระเบิด 0.5s ถึง expired | inferno (calibrate): ปกติ 72/72 ไม่โดนบล็อก, ผ่านควัน 7/7 โดนบล็อก; mirage (holdout): 150/152, 5/7. HE เจาะควันยังไม่ทำ | 🟢 |
| Visibility: FOV 50° (half-angle) | kill: มุมจากเป้าถึงจุดที่ใกล้สุด p95 5.8°, max 24.3° จึงไม่ตัด kill; ค่าเป๊ะยังไม่มีเคสพิสูจน์ | 🟡 |
| Aim: shots_fired ไม่นับลูกซอง | mirage holdout: J mag7 7, B mag7 5, Boonrywaa mag7 1 = ส่วนเกินพอดี; ch4dum sawedoff, idontgiveafaq xm1014 | 🟢 (inferno ไม่มีลูกซอง) |
| Aim: ไม่นับนัดใน tick ที่คนยิงตาย | mirage: ch4dum 1, idontgiveafaq 1, o2donggg 3, yyh 1 = ส่วนเกินที่เหลือพอดี | 🟢 |
| Aim: นัดหลัง round_end นับ | inferno: Chainnizy 46 นัด, ch4dum 5, yyh 16, Wagga 18 | 🟢 (mirage ไม่ขัด) |
| Aim: hit = player_hurt ปืนใน tick เดียวกับ weapon_fire (ทุก hurt มี fire tick เดียวกัน) | accuracy_all 20/20 | ✅ |
| Head accuracy: ไม่นับ AWP | inferno ch4dum 0.83 (ถ้านับ AWP = 0.35) | 🟢 |
| Head accuracy: ไม่นับลูกซอง | mirage: นับลูกซอง 5/10, ไม่นับ 9/10 | 🟢 |
| Head accuracy: นัดที่โดน 2 คน (หัว + อก) ไม่นับเป็นหัว | inferno Wagga r11, mirage PeterGooners r13 (ลำดับ event = หัวก่อน); "ใช้ hurt สุดท้ายของนัด" ก็อธิบายได้ | ✅ ผล / 🟡 กฎเป๊ะ |
| Head accuracy: SSG08 / auto-sniper นับไหม | ไม่มี hit ด้วย SSG / SCAR / G3 ใน 2 แมตช์ (ตอนนี้นับ) | 🟡 |
| Head accuracy: คนไม่มี hit ได้ null หรือ 0 | ทุกคนมี hit (ตอนนี้ให้ null; validate ถือว่า null = 0 ok) | 🟡 |
| Counter-strafe ไม่นับ sniper | ch4dum (AWP) null ทั้งใน Leetify และของเรา | 🟢 |
| **Death จากการออกเกม** (`kills.by_disconnect`): suicide/world ที่ tick เดียวกับ `player_disconnect` ของคนตาย (±1 tick). เจอ 5 ครั้งใน 2 แมตช์ (Suzy ระหว่างแมตช์, ที่เหลือหลังจบแมตช์). **General ยังนับเป็น death** (Leetify: Suzy deaths 13) และ KAST ไม่เปลี่ยน; ใช้แค่ clutch outcome. J ใน mirage หลุดกลางเกม 2 ครั้งแต่ไม่มี death เกิดขึ้น | 5 เคส | ✅ ตรวจจับ / 🟢 ผลต่อ clutch |
