# Parameter Reference

คำอธิบายทุก parameter ที่ Leetify แสดง จัดตามหมวด ใช้เป็น reference ตอนออกแบบ metric registry ของ ImpactAgent

- **นิยาม/วิธีคำนวณเชิงลึก** → [`leetify-metrics-spec.md`](leetify-metrics-spec.md)
- **อยู่หน้าไหนในเว็บ** → [`../research/leetify-sitemap.md`](../research/leetify-sitemap.md)
- **ตัวอย่างค่า** มาจากแมตช์ Dust2 13:9 (2026-08-12) ของ ch4dum ซึ่งเรามีไฟล์ `.dem` อยู่ (`dust2win.dem`)

**คอลัมน์:** *Dir* = ทิศทางที่ดี (↑ ยิ่งมากยิ่งดี, ↓ ยิ่งน้อยยิ่งดี, – ไม่มีดี/แย่) · *API* = ชื่อ field ใน Leetify Public API v2 · **สถานะ:** ✅ นิยามชัด · 🟡 รู้หลักการ ต้อง calibrate · 🔴 Leetify ไม่เปิดเผยสูตร · ❓ ยังไม่รู้นิยาม

---

## 1. Ratings

| Parameter | API | หน่วย/ช่วง | Dir | ความหมาย | ตัวอย่าง | สถานะ |
|---|---|---|---|---|---|---|
| Leetify Rating | `leetify_rating` | ± (ศูนย์กลาง 0) | ↑ | ค่าเฉลี่ยของ rating รายรอบ โดยแต่ละรอบคือ % ของ round win probability ที่เราทำให้ทีมได้หรือเสีย | +10.85 | 🔴 |
| Leetify Rating (CT) | `ct_leetify_rating` | ± | ↑ | เหมือนกัน แต่เฉลี่ยเฉพาะรอบ CT | +22.80 | 🔴 |
| Leetify Rating (T) | `t_leetify_rating` | ± | ↑ | เฉพาะรอบ T | +0.89 | 🔴 |
| Personal Performance | – | ± | ↑ | ไม่มีนิยามทางการ น่าจะเป็น rating ที่ตัดผลของทีม/โชคออก | +6.86 | ❓ |
| HLTV Rating 1.0 | – | ~1.0 = เฉลี่ย | ↑ | สูตร HLTV 1.0 (kills/round, survival, multi-kill) เป็นสูตรสาธารณะ | 2.25 | ✅ |
| Aim Rating | – | 0–100 | ↑ | คะแนนรวมด้าน aim โดยใน profile แสดงเป็น percentile ("Better than 93% of players") | 93 (profile) | 🔴 |
| Utility Rating | – | 0–100 | ↑ | รวม Quality + Quantity | 75 | 🔴 |
| Utility Quality Rating | – | 0–100 | ↑ | ใช้ utility ได้ดีแค่ไหน (flash โดนศัตรู, HE damage, flash assist) | 61 | 🔴 |
| Utility Quantity Rating | – | 0–100 | ↑ | ใช้ utility มากพอไหม | 92 | 🔴 |
| Positioning Rating | – | 0–100 | ↑ | น่าจะคิดจาก trade, opening duel, การรอด | 70 (profile) | 🔴 |
| Clutching (profile) | – | ± | ↑ | rating ส่วนที่มาจาก clutch | +15.60 | 🔴 |
| Opening Duels (profile) | – | ± | ↑ | rating ส่วนที่มาจาก opening duel | +3.91 | 🔴 |

**Label ของ Leetify Rating:** Great > +5.12 · Good +2.09…+5.12 · Average ±2.09 · Subpar −5.12…−2.09 · Poor < −5.12
**Label ของ metric อื่น** (Great/Average/Subpar/Poor) ตัดสินจากการเทียบกับค่าเฉลี่ยของ rank bracket ส่วนเกณฑ์ที่ใช้ตัดยังไม่รู้ ❓

### 1.1 Rating Breakdown (แยก Leetify Rating ตามสถานการณ์) 🟡
ผลรวมของทุกหมวดหารด้วยจำนวนรอบ = Leetify Rating **(ยืนยันแล้ว: 238.65 ÷ 22 รอบ = +10.85)**

| หมวด | ความหมาย (จาก tooltip ของ Leetify) | ตัวอย่าง (ผลรวมทั้งแมตช์) |
|---|---|---|
| Mid-round K/D | การดวลที่เกิดหลัง opening duel แต่ก่อน plant ระเบิด | +89.94 |
| Opening Duels | ได้ kill แรก หรือเป็นคนตายคนแรกของรอบ | +64.75 |
| Retakes | rating ที่ได้/เสียตอนเป็น CT หลังระเบิดถูก plant | +55.70 |
| Clutches | ชนะรอบในฐานะคนสุดท้ายที่รอดของทีม | +17.24 |
| Damage Assists | ทำ damage ที่ช่วยให้เพื่อนได้ kill | +6.54 |
| Traded | rating ที่ได้คืนเมื่อการตายของเราช่วยให้เพื่อนได้ kill | +3.94 |
| Flash Assists | ศัตรูตายตอนตาบอดจาก flash ของเรา | +2.18 |
| Afterplants | rating ที่ได้/เสียตอนเป็น T หลัง plant | +0.92 |
| Enemy Saving | credit จากการชนะรอบที่ศัตรูยังมีคนรอด (หักลบด้วยมูลค่าอุปกรณ์ที่ศัตรู save ไว้) | −2.56 |

- **รายรอบ:** rating ของรอบ + label (GREAT/GOOD/AVERAGE/SUBPAR) + หมวดที่ทำให้ได้/เสีย rating + ลิงก์ "Watch in 2D Replay" เช่น Round 16 (CT, WON): +103.12 = Clutches +58.76, Mid-round K/D +44.36
- **Consistency:** แสดง rating จริงเทียบกับค่าที่คาดไว้ แล้วให้ label OVERPERFORMING / ON PAR

---

## 2. General

| Parameter | API | หน่วย | Dir | ความหมาย | ตัวอย่าง | สถานะ |
|---|---|---|---|---|---|---|
| Kills / Deaths / Assists | `total_kills` / `total_deaths` / `total_assists` | ครั้ง | ↑/↓/↑ | | 33 / 15 / 4 | ✅ |
| Kill Difference | – | ครั้ง | ↑ | kills − deaths | +18 | ✅ |
| K/D | `kd_ratio` | อัตราส่วน | ↑ | | 2.20 | ✅ |
| Total Damage | `total_damage` | HP | ↑ | | 3093 | ✅ |
| ADR | `dpr` | HP/รอบ | ↑ | damage ต่อรอบ | 141 | ✅ |
| KAST | `kast` | % | ↑ | % รอบที่ได้ Kill / Assist / Survive / ถูก Trade | 86% | 🟡 ต้องรู้ trade window |
| Rounds Survived | `rounds_survived` | รอบ (%) | – | | 7 (32%) | ✅ |
| 2K/3K/4K/5K | `multi2k`… | รอบ | ↑ | จำนวนรอบที่ได้ N kill | 5 / 2 / 0 | ✅ |
| HS Kill % | – | % | ↑ | kill ที่ปิดด้วย headshot ÷ kills | 52% | ✅ |
| Wasted Magazine % | – | % (กระสุน) | ↓ | น่าจะเป็นกระสุนที่ค้างในแม็กตอนตายหรือตอน reload ทิ้ง | 13% (17 bullets) | ❓ |
| Shots Fired | `shots_fired` | นัด | – | | 333 | ✅ |
| Score / MVPs | `score` / `mvps` | | ↑ | จาก scoreboard ในเกม | 72 / 6 | ✅ |

---

## 3. Aim

| Parameter | API | หน่วย | Dir | ความหมาย | ตัวอย่าง | สถานะ |
|---|---|---|---|---|---|---|
| Accuracy (Enemy Spotted) | `accuracy_enemy_spotted` | % | ↑ | hit ÷ shot เฉพาะตอนที่เห็นศัตรู **(เป็นตัวหลัก)** | 41% | ✅ |
| Accuracy (All Shots) | `accuracy` | % | ↑ | hit ÷ shot ทั้งหมด | 24% | ✅ |
| Headshot Accuracy | `accuracy_head` | % | ↑ | hit ที่หัว ÷ hit ศัตรูทั้งหมด (ไม่นับ AWP) | 25% | ✅ |
| Spray Accuracy | `spray_accuracy` | % | ↑ | เฉพาะ rifle ที่ยิงต่อเนื่อง ≥ 3 นัดตอนเห็นศัตรู: hit ÷ shot | 38% | ✅ |
| Proper Counter-Strafing | `counter_strafing_shots_good_ratio` | % | ↑ | นัด rifle ที่ยิงตอนความเร็ว < 34% ของ max speed ไม่นับตอนนั่ง | 83% | ✅ |
| Crosshair Placement | `preaim` | องศา | ↓ | มุมที่เป้าต้องขยับ ระหว่างตอนเห็นศัตรูครั้งแรกกับตอน damage ครั้งแรก (median) | 4.96° | ✅ |
| Time to Damage | `reaction_time` | ms | ↓ | เวลาจากเห็นศัตรูครั้งแรกถึง damage ครั้งแรก ไม่นับค่า ≥ 1s (median) | 586 ms | ✅ |
| Time to Kill | – | ms | ↓ | น่าจะเป็นเวลาจาก damage แรกถึงตอน kill | n/a ในแมตช์นี้ | ❓ |
| First Bullet Accuracy | – | % | ↑ | นัดแรกของการดวลโดนไหม | n/a ในแมตช์นี้ | ❓ |

> Time to Kill กับ First Bullet ขึ้น n/a ทุกคนในแมตช์นี้ อาจเป็นเพราะเป็น metric ใหม่ที่ไม่ได้คำนวณย้อนหลัง หรือไม่มีให้กับ demo จาก Matchmaking

---

## 4. Positioning: Opening Duels & Trades

| Parameter | API | หน่วย | Dir | ความหมาย | ตัวอย่าง | สถานะ |
|---|---|---|---|---|---|---|
| Opening Duel Attempts % (CT/T/รวม) | – | % | – | % รอบที่เราอยู่ในการดวลแรกของรอบ | 18% | ✅ |
| Opening Duel Success % | – | % | ↑ | % ที่ชนะการดวลแรก | 100% | ✅ |
| Opening Duel Traded % | – | % | ↑ | เมื่อแพ้การดวลแรก เพื่อน trade คืนได้กี่ % | 0% | 🟡 |
| CT Opening Duels won without being traded | – | ครั้ง | ↑ | | | 🟡 |
| Trade Kill Opportunities | `trade_kill_opportunities` | ครั้ง | – | จังหวะที่เพื่อนตาย และเรามีโอกาส trade | 10 | 🟡 |
| Trade Kill Attempts | `trade_kill_attempts` | ครั้ง (%) | ↑ | ได้พยายาม trade | 10 (100%) | 🟡 |
| Trade Kill Success | `trade_kills_succeed` | ครั้ง (%) | ↑ | trade สำเร็จ | 6 (60%) | 🟡 |
| Traded Death Opportunities | `traded_death_opportunities` | ครั้ง | – | จังหวะที่เราตาย และเพื่อนมีโอกาส trade ให้ | 5 | 🟡 |
| Traded Death Attempts | `traded_death_attempts` | ครั้ง (%) | ↑ | เพื่อนพยายาม trade ให้ | 2 (40%) | 🟡 |
| Traded Deaths Success | `traded_deaths_succeed` | ครั้ง (%) | ↑ | เพื่อน trade ให้สำเร็จ | 1 (50%) | 🟡 |
| Most Killed Player / Most Died To | – | ชื่อ | – | คู่ปรับในการดวลแรก | Touch And Go / – | ✅ |

**Opening Duel Round Breakdown (ต่อรอบ):** Round · Attacker · Attacker Side · Attacker Weapon · Victim · Victim Side · Round Time (วินาทีนับจากเริ่มรอบ)

---

## 5. Clutches

| Parameter | หน่วย | ความหมาย | ตัวอย่าง (ทีมเรา) |
|---|---|---|---|
| Clutch Win Rate | % | clutch ที่ชนะ ÷ ทั้งหมด | 18% (2 won / 9 lost) |
| Saves | ครั้ง | ยอมแพ้รอบแต่รอด เก็บปืนไว้ได้ | 0 |
| Total Kills in clutches | ครั้ง (+label) | | 8 (Good) |
| รายการต่อ clutch | – | ผู้เล่น · 1vN · kills · Round · WON/LOST/SAVED | ch4dum 1v1, 1 kill, R16, WON |

นิยาม clutch: เป็นคนสุดท้ายที่รอดของทีม แล้วนับ 1vN จากจำนวนศัตรูที่เหลือ ณ ตอนนั้น ✅

---

## 6. Utility

| Parameter | API | หน่วย | Dir | ความหมาย | ตัวอย่าง | สถานะ |
|---|---|---|---|---|---|---|
| Flashes / Smokes / HEs / Molotovs thrown | `flashbang_thrown`… | ลูก | – | | 22 / 15 / 7 / 14 | ✅ |
| Enemies Flashed per Flashbang | – | คน/ลูก | ↑ | ศัตรูที่ตาบอด > 1.1s ÷ flash ที่โยน | 0.55 | ✅ |
| Friends Flashed per Flashbang | – | คน/ลูก | ↓ | นับเพื่อนรวมตัวเองด้วย | 0.55 | ✅ |
| Flash Blind Duration per Flashed Enemy | `flashbang_hit_foe_avg_duration` | วินาที | ↑ | ต่อ flash เอาค่าตาบอดนานสุดของศัตรู แล้วเฉลี่ย | 2.9 s | ✅ |
| Flash Assists | `flash_assist` | % / ครั้ง | ↑ | ในตาราง utility แสดงเป็น % | 5% | 🟡 ตัวหารไม่ชัด |
| Flashbangs Leading to Kills | `flashbang_leading_to_kill` | % | ↑ | ศัตรูตายตอนตาบอดจาก flash ของเรา | | ✅ |
| Total Enemies Flashed (+Duration) | `flashbang_hit_foe` | คน / s | ↑ | | 12 | ✅ |
| Damage to Enemies per HE | `he_foes_damage_avg` | HP/ลูก | ↑ | | 18.00 | ✅ |
| Damage to Teammates per HE | `he_friends_damage_avg` | HP/ลูก | ↓ | | 0.14 | ✅ |
| Total HE / Molotov Damage | – | HP | ↑ | | 126 / 38 | ✅ |
| Unused Utility on Death | `utility_on_death_avg` | $ | ↓ | มูลค่าระเบิดที่ถือตอนตาย เฉลี่ยต่อการตาย | 225 $ | ✅ |
| [CT] Smokes That Stopped a Push | – | % | ↑ | smoke CT ที่มีศัตรูอยู่ใน 800 units จากจุดที่ควันบาน | | 🟡 |
| Team utility mix | – | ลูก (%) | – | สัดส่วน flash/smoke/HE/molotov ของทั้งทีม | 224 ลูก: 39/26/14/21% | ✅ |

---

## 7. Timeline (กราฟสะสมรายรอบ)
เลือกเส้นได้: Kills · Deaths · Damage · AWP Kills · Enemies Flashed · Round Difference · Team Economy ✅ (ทั้งหมดได้จาก event ต่อรอบ)

## 8. Head to Head (เราเทียบกับศัตรูทีละคน)
ต่อคู่: Kills · Damage · Weapon breakdown (Snipers/Rifles/Pistols) · Spotted Accuracy (hit/fired) · Time to Damage · Crosshair Placement · Counter-Strafing · flash ที่ทำให้อีกฝ่ายตาบอด (จำนวน + วินาทีรวม) · มีโหมด Simple View กับ Matrix View
→ เป็น metric เดียวกับ Aim และ Utility แต่กรองเฉพาะคู่ attacker↔victim **ถ้าเก็บข้อมูลระดับ engagement ไว้ ก็ได้หน้านี้ฟรี**

---

## 9. ❓ ต้องหาคำตอบต่อ
1. Wasted Magazine % นิยามจริงคืออะไร
2. Personal Performance คำนวณยังไง
3. สูตรของ Aim / Utility / Positioning Rating (0–100) และการแปลงเป็น percentile
4. Flash Assists แสดงเป็น % แต่หารด้วยอะไร
5. Time to Kill / First Bullet Accuracy ทำไมขึ้น n/a
6. เกณฑ์ label Great/Average/Subpar/Poor ของแต่ละ metric
