# Backend Design v0.1 (Phase 3)

แผน backend ของ ImpactAgent: อัป `.dem` → queue → worker (parse + metrics + ratings) → Postgres + Parquet → FastAPI. โครงข้อมูลอ้างอิง [`data-model.md`](data-model.md) (โค้ดต้องตรงกับสองไฟล์นี้; ถ้าต้องเปลี่ยน ให้แก้ doc ใน change เดียวกัน)

> สถานะ: v0.1 = แผนที่ owner อนุมัติ (2026-11-06) ยังไม่มีโค้ด ลำดับงานอยู่ใน §12 และ `docs/roadmap.md` Phase 3

---

## 0. การตัดสินใจที่ล็อกแล้ว

| เรื่อง | ตัดสินใจ |
|---|---|
| DB + Auth | Supabase (Postgres) · login Steam OpenID ทำเองใน FastAPI → สร้าง/หา user ใน `auth.users` ผ่าน Admin API · session = JWT ของเราเอง (cookie) |
| Storage | Cloudflare R2 · อัปตรงจาก browser ด้วย presigned PUT · รับ `.dem`, `.dem.bz2`, `.dem.gz`, `.dem.zst` |
| Job | ตาราง `jobs` ใน Supabase เป็น queue → worker แบบ pull (Docker) บน laptop → ย้ายไป VPS ภายหลัง |
| ข้อมูล | event ละเอียดเป็น Parquet ใน R2 · Postgres เก็บแค่ summary ที่หน้าเว็บ query บ่อย · ลบ `.dem` หลัง parse สำเร็จ |
| Metric ใน PG | **jsonb ต่อ (match, player)** แทน long `metric_values` (long format อยู่ใน Parquet) |
| `kills` | **Parquet อย่างเดียว** (ไม่ลง PG) |
| การมองเห็น | แมตช์ **unlisted** (มีลิงก์ก็ดูได้) · หน้า profile เฉพาะคนที่ login Steam แล้ว · อีก 9 คนเห็นแค่ในหน้าแมตช์ · มีทางขอลบข้อมูล (§9) |
| Replay | ตำแหน่ง 8 Hz **เก็บตั้งแต่ parse** (ช่วง 3.1b) UI ทำหลัง MVP |
| Demo ที่ fail | ย้ายไป `failed/` เก็บ 7 วัน (R2 lifecycle) |
| Limit | ไฟล์ที่อัป ≤ 512 MB · .dem หลังแตก ≤ 1 GiB (`MAX_DEMO_BYTES`) · 10 upload/วัน/user |
| LLM | Gemini free tier ช่วง beta + เขียนใน Privacy Policy ว่า prompt อาจถูก Google ใช้ |
| Package | `server/` แพ็กเดียว (`iaserver`) มี pipeline / core / api / worker |
| Hosting (beta) | API + worker อยู่ใน docker-compose เดียวกันบน laptop + Cloudflare Tunnel (`api.tammapol.com`) → ย้ายไป VPS ทั้งคู่เมื่อคนเยอะ |
| ข้อมูลภายนอก | ไม่เก็บข้อมูล Leetify / FACEIT ใน product (truth file อยู่ใน `data/validation/` ที่ gitignore สำหรับ validate เท่านั้น) |

---

## 1. Architecture

```
Browser (Vercel, impactagent.tammapol.com)
  │ 1. sha256 ไฟล์ (hash-wasm) → POST /uploads
  │ 2. PUT ไฟล์ตรงไป R2 (presigned, ไม่ผ่าน API / Tunnel)
  │ 3. POST /uploads/{id}/complete → poll GET /uploads/{id}
  ▼
Cloudflare Tunnel (api.tammapol.com) ──▶ FastAPI  ─┐
                                                   ├─ Postgres (Supabase): users, matches, jobs, summary
laptop: docker-compose ── worker (pull) ───────────┤
                         cloudflared               └─ R2: incoming/ failed/ matches/{id}/…
```

- **Upload ไม่ผ่าน Tunnel:** Cloudflare (free) จำกัด request body 100 MB ถ้าส่งไฟล์ผ่าน API จะติด limit นี้ จึงให้ browser PUT ตรงไป `<account>.r2.cloudflarestorage.com` ด้วย presigned URL
- **Laptop ดับ / sleep:** API ล่มด้วย (ยอมรับได้ช่วง beta) ส่วน job ที่ค้างอยู่ reaper จะ requeue เมื่อกลับมา (§5.4)
- **ย้ายไป VPS:** compose ไฟล์เดิม เปลี่ยนแค่ `.env` + Tunnel token (หรือเปิด port ตรง) ไม่ต้องแก้โค้ด

---

## 2. Postgres schema

**หลักการ:** PG เก็บสิ่งที่ (ก) หน้าเว็บ query บ่อย (ข) ต้อง join/aggregate ข้ามแมตช์ (ค) เป็นสถานะงาน/บัญชี ที่เหลือ (event ทุกชนิด) อยู่ Parquet ต่อแมตช์

```sql
-- บัญชี (user_id = auth.users.id ที่สร้างผ่าน Admin API ตอน login Steam ครั้งแรก)
profiles(user_id uuid PK → auth.users(id) ON DELETE CASCADE,
         steam_id text UNIQUE NOT NULL CHECK (steam_id ~ '^\d{17}$'),
         persona_name text, avatar_url text,
         is_admin bool NOT NULL DEFAULT false,
         created_at timestamptz, last_login_at timestamptz)

matches(match_id uuid PK DEFAULT gen_random_uuid(),   -- uuid v4 = ลิงก์ unlisted (เดาไม่ได้)
        dem_sha256 text UNIQUE NOT NULL,              -- hash ของ .dem หลังแตกไฟล์ = key กันซ้ำตัวจริง
        fingerprint text,                             -- map|rounds|score|steam_ids (wp_states.match_fingerprint)
        map text, tickrate int, rounds_played int, score_a int, score_b int, winner text,
        client_build int, played_at timestamptz NULL, -- demo MM อาจไม่มีวันที่ → fallback created_at
        pipeline_version text → pipeline_versions,
        created_at timestamptz)
  INDEX (fingerprint), INDEX (map)

match_players(match_id, steam_id  PK,
              name text, team text CHECK (team IN ('a','b')),
              played_at timestamptz, map text,             -- denormalize ให้ profile เรียงตามเวลาได้ด้วย index เดียว
              rounds_played int, kills int, deaths int, assists int,
              adr real, kast_pct real, hs_pct real, impact real,   -- คอลัมน์ที่ scoreboard / list ใช้
              metrics jsonb NOT NULL,   -- {"all": {"<metric_id>": [value, num, den], ...}} (§2.1)
              redacted bool NOT NULL DEFAULT false)        -- §9
  INDEX (steam_id, played_at DESC)

rounds(match_id, round_no PK, winner_side, win_reason, ct_team, plant_site,
       ct_equip_value, t_equip_value, ct_buy_type, t_buy_type)

player_rounds(match_id, round_no, steam_id PK, side, kills, deaths, assists, damage,
              survived, was_traded, kast, equip_value, rating)   -- ~240 แถว/แมตช์: timeline + economy split ข้ามแมตช์

user_matches(user_id, match_id PK, relation text DEFAULT 'uploader', created_at)
  INDEX (user_id, created_at DESC)

-- คำขอของ user (1 แถวต่อการกดอัป) แยกจาก job (1 งานต่อไฟล์) ดู §5.3
upload_requests(request_id uuid PK, user_id → profiles, job_id → jobs NULL, match_id NULL,
                filename text, ext text, declared_size bigint, declared_sha256 text,
                status text,   -- awaiting_upload | processing | done | failed | canceled | expired
                created_at, finished_at)
  INDEX (user_id, created_at DESC), INDEX (job_id)

jobs(job_id uuid PK, kind text CHECK (kind IN ('ingest','recompute','redact')),
     status job_status, stage text,          -- §5.1
     upload_key text, ext text, declared_size bigint, declared_sha256 text,
     upload_sha256 text, dem_sha256 text, match_id uuid NULL, target_version text NULL,
     attempts int DEFAULT 0, max_attempts int DEFAULT 3, run_after timestamptz DEFAULT now(),
     locked_by text, locked_at timestamptz, heartbeat_at timestamptz,
     fault text NULL CHECK (fault IN ('input','infra','ours')),   -- §5.6
     error_code text, error_message text, progress jsonb,
     created_at, updated_at, finished_at)
  INDEX (status, run_after) WHERE status IN ('queued','retry_wait')
  UNIQUE (declared_sha256) WHERE kind = 'ingest' AND status IN ('awaiting_upload','queued','running','retry_wait')

job_errors(id bigserial PK, job_id → jobs, attempt int, stage text, worker_id text,
           pipeline_version text, error_code text, message text, traceback text, created_at)

workers(worker_id text PK, hostname, version, started_at, heartbeat_at, status, current_job_id)

pipeline_versions(version text PK, parse_version text, metrics_version text, wp_model text,
                  credit_version text, impact_spec text, git_sha text, components jsonb,
                  is_current bool, created_at)
  UNIQUE (is_current) WHERE is_current

match_artifacts(match_id, layer text CHECK (layer IN ('events','snapshot','derived','replay')), version  PK,
                r2_prefix text, bytes bigint, files jsonb, created_at)

redactions(steam_id text PK, requested_by uuid → profiles, scope text, created_at, applied_at)   -- §9
```

### 2.1 `match_players.metrics` (jsonb)
- โครง: `{"all": {"adr": [value, num, den], "ttd": [value, null, null], ...}}` ทุก `id` ใน `impactagent/metrics/registry.yaml` · ใส่ `"CT"` / `"T"` เมื่อ `compute_match_metrics` มี scope แยก (ตอนนี้มีแค่ `all` + `impact_ct` / `impact_t`)
- รวมข้ามแมตช์ = Σnum / Σden (data-model §1.3) เช่น `sum((metrics->'all'->'adr'->>1)::float8) / sum((metrics->'all'->'adr'->>2)::float8)` · metric `median` คิดจาก Parquet (`engagements`) ไม่ใช่จาก jsonb
- เหตุผล: long format = 56 metric × 10 คน × 3 scope ≈ 1.7k แถว (~300 KB รวม index) ต่อแมตช์ → PG ทั้งหมด ~0.35 MB/แมตช์ = ~1.4k แมตช์บน Supabase free 500 MB; jsonb ~10 แถว (~80 KB/แมตช์ รวมตารางอื่น) = ~6k แมตช์ · long format ยังเขียนเป็น `metric_values.parquet` ให้ LLM / DuckDB

### 2.2 อะไรอยู่ที่ไหน
| Postgres | Parquet (R2, ต่อแมตช์) |
|---|---|
| profiles, matches, match_players (+ metrics jsonb), rounds, player_rounds, user_matches, upload_requests, jobs, job_errors, workers, pipeline_versions, match_artifacts, redactions | rounds, players, player_rounds_side, **kills**, damages, shots, grenades, detonations, blinds, bomb, death_inventory, smokes, engagements, trade_windows, player_zones · state_snapshots, defuse_starts · wp_states, rating_events, player_round_ratings, player_rounds, clutches, metric_values (long) · replay |

### 2.3 RLS และ role
- เปิด RLS ทุกตาราง, **ไม่มี policy ให้ `anon`** (anon key หลุดก็อ่านไม่ได้) · frontend ไม่คุยกับ Supabase ตรงใน MVP
- `api_role` (FastAPI, login ผ่าน pooler): DML ทุกตาราง ไม่มี DDL · auth ตรวจในโค้ด
- `worker_role` (laptop): `jobs` ผ่าน function `claim_job(worker_id)`, `heartbeat_job(job_id, worker_id, stage, progress)`, `finish_job(...)`, `fail_job(...)` เท่านั้น · UPSERT `matches`, `match_players`, `rounds`, `player_rounds`, `match_artifacts`, `user_matches` (ผ่าน `finish_job`), INSERT `job_errors`, upsert `workers`, `pipeline_versions` · **อ่าน `profiles` ไม่ได้**
- policy แบบ `auth.uid()` (เช่น `user_matches.user_id = auth.uid()`) เขียนเผื่อไว้ได้ ใช้เมื่อเปิดให้ supabase-js อ่านตรง

---

## 3. Layout ใน R2 (bucket เดียว แยกด้วย prefix)

```
incoming/{job_id}/upload.{dem|dem.bz2|dem.gz|dem.zst}   lifecycle: ลบหลัง 2 วัน (กันไฟล์ค้าง)
failed/{job_id}/upload.<ext> + error.json                lifecycle: ลบหลัง 7 วัน
matches/{match_id}/
  manifest.json                         version ทุกชั้น + ไฟล์ + rows + sha256 ของแต่ละไฟล์
  events/p{N}/{table}.parquet           ชั้น parse (สร้างใหม่ได้เฉพาะเมื่อมี demo)
  snapshot/p{N}/state_ticks.parquet     §6
                defuse_starts.parquet
                header.json             cvars (mp_roundtime, mp_c4timer, …), tickrate, client_build, map
  derived/{pipeline_version}/           wp_states, rating_events, player_round_ratings, player_rounds,
                                        clutches, player_zones, metric_values.parquet
  replay/r{N}/meta.json                 player index ↔ steam_id, tick ของแต่ละรอบ, scale ของ quantize
              round_{NN}.parquet        8 Hz (§6.3)
```

- **Version:**
  - `parse_version` = `p1`, `p2`, … (`server/pipeline/versions.py`, bump ด้วยมือเมื่อคอลัมน์/กฎของ parser หรือ snapshot เปลี่ยน)
  - `pipeline_version` = `p{N}-m{sha8(registry.yaml)}-{wp_model stem เช่น wp2}-c{sha8(credit.yaml)}-is{rev ของ impact-spec}` คำนวณตอน worker start จากไฟล์ใน package แล้ว upsert ลง `pipeline_versions` (`components` jsonb เก็บ git sha + hash เต็ม)
  - `replay` version `r{N}` แยก เพราะ format replay เปลี่ยนไม่ขึ้นกับ metric
- **Derived เขียน prefix ใหม่ทุก version** ไม่ทับของเดิม; `matches.pipeline_version` เปลี่ยนเมื่อ recompute สำเร็จเท่านั้น → rollback ได้ · prefix เก่าลบด้วยมือ (admin) เมื่อแน่ใจ
- ใช้ path ต่อแมตช์ (ไม่ใช่ hive partition ต่อตาราง): หน้าเว็บอ่านทีละแมตช์; query ข้ามแมตช์ได้รายการ path จาก PG แล้วให้ DuckDB อ่าน
- CORS ของ bucket: อนุญาต `PUT` จาก origin ของ frontend เท่านั้น · token R2 ของ worker / API scope แค่ bucket นี้

---

## 4. Upload limits และการตรวจไฟล์
- `POST /uploads` ปฏิเสธถ้า `declared_size` > 512 MB, นามสกุลไม่อยู่ใน allow-list, หรือเกิน 10 request/วัน/user (นับ `upload_requests` 24 ชม.ล่าสุด, ไม่นับ `canceled`/`expired`)
- presigned PUT อายุ 15 นาที, ตรึง `Content-Length` = `declared_size` · `complete` ทำ `HEAD` เช็คขนาดซ้ำ
- worker ตรวจ magic bytes ตามนามสกุล (`PBDEMS2` / `BZh` / gzip `1f 8b` / zstd `28 b5 2f fd`), hash ไฟล์เอง (`upload_sha256`, ไม่เชื่อ client), แตกไฟล์ภายใต้ `MAX_DEMO_BYTES` และ hash `.dem` (`dem_sha256`), แล้ว `parse_demo` (child process, timeout 300 s ของเดิม)

---

## 5. Jobs

### 5.1 State machine
```
awaiting_upload ─(complete + HEAD ผ่าน)─▶ queued ─claim─▶ running[stage] ─▶ done
      │                                    ▲                │
      └─ 1 ชม. ไม่ complete → expired       │                ├─ dem_sha256 มีแล้ว → duplicate (ผูก requester กับแมตช์เดิม)
                                  retry_wait ◀── transient ──┤
                                 (run_after = backoff)       └─ permanent / ครบ max_attempts → failed
running.stage: downloading → verifying → parsing → computing → storing
cancel ได้ตอน awaiting_upload / queued (ทุก request ของ job ถูก cancel) → canceled
```
`job_status` = `awaiting_upload | queued | running | retry_wait | done | duplicate | failed | canceled | expired`

### 5.2 Claim / heartbeat / reaper
- `claim_job(worker_id)`: `UPDATE jobs SET status='running', stage='downloading', locked_by=…, locked_at=now(), heartbeat_at=now(), attempts=attempts+1 WHERE job_id = (SELECT job_id FROM jobs WHERE status IN ('queued','retry_wait') AND run_after <= now() ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *`
- worker ส่ง heartbeat ทุก 30 s (job + `workers`)
- reaper = `pg_cron` ทุก 1 นาที: `running` ที่ heartbeat เงียบ > 5 นาที → `retry_wait` (หรือ `failed` ถ้าครบ attempts, `fault='infra'`) · `awaiting_upload` > 1 ชม. → `expired`
- ทุกขั้นเป็น idempotent: R2 เขียน path ตาม version (ทับได้), PG upsert ใน transaction เดียวใน `finish_job` (รวมการผูก `user_matches` ของทุก requester)

### 5.3 กันอัปซ้ำ และหลายคนอัปไฟล์เดียวกันพร้อมกัน
แยก **`upload_requests`** (ของ user, 1 แถวต่อการกดอัป) ออกจาก **`jobs`** (ของระบบ, 1 งานต่อไฟล์) user เห็นแค่ request ของตัวเอง; ทุก request ที่ชี้ job เดียวกันได้แมตช์เข้าบัญชีพร้อมกันตอน job จบ

`POST /uploads {filename, size, sha256}` ใน transaction เดียว:
1. มี `matches` ที่ upload นี้เคยสร้าง (หา `jobs.upload_sha256 = sha256 AND status='done'`) → สร้าง request `done` + `user_matches` ทันที, ไม่ต้องอัป
2. มี job ingest ที่ยัง active ด้วย `declared_sha256` เดียวกัน (unique partial index) → สร้าง request ผูก job เดิม (`processing`) ไม่ต้องอัป ถ้า job นั้นยัง `awaiting_upload` คนที่มาทีหลังได้ presigned URL ของ key เดียวกันด้วย (ใครอัปเสร็จก่อนก็ complete ได้)
3. ไม่งั้น → สร้าง job `awaiting_upload` + request + presigned URL

`finish_job` (done หรือ duplicate) → `UPDATE upload_requests SET status='done', match_id=… WHERE job_id=…` + `INSERT user_matches … ON CONFLICT DO NOTHING` สำหรับทุก request ของ job ใน transaction เดียวกับการเขียนแมตช์ · `fail_job` (ถาวร) → request ทั้งหมด `failed` (user อัปใหม่ได้)

ชั้นกันซ้ำ:
| ชั้น | key | จับกรณี |
|---|---|---|
| request | `declared_sha256` (browser hash) | คนเดิม/หลายคนอัปไฟล์เดียวกันพร้อมกันหรือภายหลัง |
| worker | `upload_sha256` ตรวจซ้ำ ถ้าไม่ตรงกับที่ประกาศ → ใช้ค่าจริงแล้วเช็คใหม่ | client โกหก hash |
| match | `dem_sha256` UNIQUE | ไฟล์ต่างกันแต่ .dem เดียวกัน (`.dem` vs `.dem.bz2`) → job เป็น `duplicate` ผูก requester กับแมตช์เดิม |
| content | `fingerprint` | demo คนละไฟล์ของแมตช์เดียวกัน: log + แสดงใน admin ไม่ block |

ข้อสังเกต: ข้อ 1–2 ให้แมตช์กับคนที่รู้ hash โดยไม่ต้องอัปไฟล์ ยอมรับได้เพราะแมตช์เป็น unlisted อยู่แล้ว และการรู้ sha256 ของไฟล์ ~100–300 MB เท่ากับมีไฟล์

### 5.4 Retry
| ประเภท (`fault`) | ตัวอย่าง | การจัดการ |
|---|---|---|
| `infra` (transient) | network R2/PG, worker crash/heartbeat หาย, `ParseTimeoutError` | `retry_wait` backoff 1 → 5 → 30 นาที, `max_attempts` 3 (timeout retry 1 ครั้ง: อาจเป็นเพราะ laptop โหลดหนัก) |
| `input` (permanent) | magic bytes ผิด, `DemoTooLargeError`, header ไม่ใช่ demo ที่รองรับ, ไฟล์เสีย | `failed` ทันที, ข้อความบอก user ว่าไฟล์มีปัญหา |
| `ours` (permanent) | `check_invariants` ไม่ผ่าน, exception ใน metric/ratings, parse error ที่เกิดซ้ำทุก attempt | `failed`, ข้อความบอก user ว่าเป็นปัญหาฝั่งเรา, เข้า admin (§5.6) |

### 5.5 ไฟล์ demo
- สำเร็จ (`done` / `duplicate`) → ลบ `incoming/{job_id}/` ทันที
- `failed` → ย้ายไป `failed/{job_id}/` + `error.json` (code, stage, versions) · lifecycle ลบหลัง 7 วัน · ภายใน 7 วัน admin กด retry ได้ (§5.6)
- `expired` / `canceled` → ลบ (ถ้ามี)

### 5.6 Admin: job ที่ fail จากบั๊กของเรา
- ทุก attempt ที่ error เขียน `job_errors` (stage, worker, pipeline_version, error_code, traceback)
- `GET /admin/jobs?status=failed&fault=ours` (default ของหน้า admin), `GET /admin/jobs/{id}` (requests, errors, versions, ลิงก์ `failed/` ถ้ายังไม่หมดอายุ)
- `POST /admin/jobs/{id}/retry` → ถ้า demo ยังอยู่ใน `failed/` ย้ายกลับ `incoming/` แล้ว `queued` (attempts รีเซ็ต) · ใช้หลังแก้บั๊กและ bump version
- แจ้งเตือน (ทางเลือก, env `ADMIN_WEBHOOK_URL`): ส่ง webhook เมื่อมี `fault='ours'` ใหม่
- admin = `profiles.is_admin` · ป้องกันเพิ่มด้วย Cloudflare Access บน path `/admin/*`

---

## 6. Recompute โดยไม่มี demo

### 6.1 อะไรเปลี่ยนแล้วต้องใช้อะไร
| สิ่งที่เปลี่ยน | ใช้ | ต้องมี demo? |
|---|---|---|
| ค่าสัมประสิทธิ์ WP (feature เดิม) | `wp_states` | ไม่ |
| `credit.yaml` / กฎ credit | wp_states + kills, damages, trade_windows, rounds, players | ไม่ |
| สูตร metric บนคอลัมน์ที่มี | event tables | ไม่ |
| feature WP ใหม่จาก prop ที่อยู่ใน snapshot | `state_ticks` | ไม่ |
| state ชนิดใหม่ (เช่น `begin_defuse`) | `state_ticks` ต้องมี tick นั้น → เก็บ tick ของ begindefuse ไว้ล่วงหน้า | ไม่ |
| visibility / aim / trade feature, prop ที่ไม่ได้เก็บ | tick data | **ต้องมี** → ใช้ได้กับแมตช์ใหม่เท่านั้น (replay 8 Hz ช่วยได้บางส่วน) |

### 6.2 `state_ticks` / `defuse_starts` / `header.json` (ใหม่)
ตอนนี้ `build_wp_states` เปิด `.dem` อีกรอบเพื่ออ่าน `server_cvar`, `bomb_begindefuse` (`haskit`) และ tick ณ state (`team_num`, `current_equip_value`, `has_defuser`, `is_defusing`) ถ้าไม่เก็บไว้ ลบ demo แล้วจะสร้าง wp_states ใหม่ไม่ได้
- `state_ticks`: ticks = ทุก state tick และ tick − 1 (freeze_end, kill, plant, **begindefuse**, defuse, explode, round_end) × ผู้เล่นทุกคน: `tick, steam_id, team_num, is_alive, health, armor_value, has_helmet, has_defuser, is_defusing, current_equip_value, active_weapon, X, Y, Z`
- `defuse_starts`: begin/abort ของ `bomb_begindefuse` พร้อม `haskit`
- `header.json`: cvars ทั้งหมดจาก `server_cvar`, tickrate, client_build, map
- refactor: `read_state_snapshots(dem, ticks)` แยกจาก `_read_timers_and_equip` และ `build_wp_states` รับ snapshot แทน path ได้ (ผลต้อง `equals` ของเดิมทุกแมตช์)

### 6.3 Replay 8 Hz (ช่วง 3.1b)
- ทุก 8 tick (64-tick) ระหว่าง freeze_end − 5 s ถึง round_end + 5 s · ต่อผู้เล่น: x, y, z (quantize int16 ตาม scale ใน `meta.json`), yaw (int16), pitch (int8), hp, armor, active_weapon (id), alive, flags (ducking, scoped, defusing, blind) · + เส้นทางระเบิด (entity, tick, xyz) · 1 ไฟล์ต่อรอบ, zstd
- เก็บใน child process เดียวกับ parse (ไม่เปิด demo เพิ่ม) แยกจาก event tables เพื่อให้ปิดได้ด้วย flag ถ้าช้า

### 6.4 ขนาดต่อแมตช์
วัดจาก `data/parsed` (mirage 24 รอบ) แถวที่เขียนว่าประเมินยังไม่ได้วัด (วัดจริงในช่วง 3.1 / 3.1b)
| ชั้น | ขนาด |
|---|---|
| event tables (14 ไฟล์, ยังไม่รวม engagements/smokes) | ~190 KB (วัด) |
| rating_events + player_round_ratings | ~28 + 6 KB (วัด) |
| wp_states | ~3.5 KB (วัด: 103 KB / 30 แมตช์, ~210 state/แมตช์) |
| state_ticks + defuse_starts + header | ~50–120 KB (ประเมิน: ~450 tick × 10 คน) |
| derived อื่น (player_rounds, clutches, metric_values long) | ~30–60 KB (ประเมิน) |
| **รวม ไม่มี replay** | **~0.3–0.4 MB** (demo 80–330 MB) |
| replay 8 Hz | ~1–3 MB (ประเมิน) |
| Postgres | ~80 KB (ประเมิน, metrics jsonb) |

R2 free 10 GB ≈ 4k แมตช์ (มี replay); ส่วนเกิน $0.015/GB-เดือน · Supabase free 500 MB ≈ 6k แมตช์

---

## 7. API (FastAPI)

| กลุ่ม | Endpoint |
|---|---|
| Auth | `GET /auth/steam/login?next=` · `GET /auth/steam/callback` · `POST /auth/logout` · `GET /me` · `DELETE /me` (§9) |
| Upload | `POST /uploads` `{filename, size, sha256}` → `{request_id, status: done, match_id}` หรือ `{request_id, status: processing}` หรือ `{request_id, upload_url, headers, expires_at}` · `POST /uploads/{request_id}/complete` · `GET /uploads/{request_id}` (status, stage, progress, error สำหรับ user) · `GET /me/uploads` · `DELETE /uploads/{request_id}` |
| Match | `GET /matches/{id}` (header + scoreboard จาก `match_players`) · `/matches/{id}/rounds` · `/matches/{id}/players/{steam_id}` · `/matches/{id}/kills` (Parquet) · `/matches/{id}/rating-breakdown?steam_id=` (Parquet) · `DELETE /matches/{id}` (ถอดออกจากบัญชีตัวเอง) |
| Player | `GET /players/{steam_id}` · `/players/{steam_id}/matches?cursor=` · `/players/{steam_id}/metrics?ids=&last_n=30` (Σnum/Σden) — **404 ถ้า steam_id ไม่มีใน `profiles`** |
| Privacy | `POST /me/redact` (§9) |
| Meta | `GET /registry` (label/unit/direction/format จาก registry.yaml) · `GET /health` · `GET /version` (pipeline_version ปัจจุบัน) |
| Admin | `GET /admin/jobs` · `GET /admin/jobs/{id}` · `POST /admin/jobs/{id}/retry` · `POST /admin/recompute {match_ids \| all, version}` · `GET /admin/workers` |
| Chat (Phase 4) | `POST /matches/{id}/chat` (stream) · `GET /chats/{id}` จองไว้ |

- Parquet อ่านด้วย pyarrow/DuckDB จาก R2 + LRU cache ต่อ (match_id, version, table)
- Rate limit ใช้ IP จาก `CF-Connecting-IP` (uvicorn `--proxy-headers`, เชื่อเฉพาะ cloudflared ใน compose)

---

## 8. Auth, session, cookie, CORS

**Steam OpenID 2.0:**
- `login` สร้าง nonce เก็บใน cookie สั้นๆ แล้ว redirect ไป Steam · `return_to = https://api.tammapol.com/auth/steam/callback`
- `callback` ตรวจ:
  - `return_to` ตรงกับที่ส่ง
  - nonce ตรงกับ cookie
  - POST `check_authentication` กลับไป Steam ต้องได้ `is_valid:true`
  - `claimed_id` ตรง regex `^https://steamcommunity.com/openid/id/(\d{17})$`
- ผ่านแล้วดึงชื่อ/avatar จาก Steam Web API `GetPlayerSummaries`
- หา/สร้าง `auth.users` ผ่าน Admin API (ไม่ใช้ email จริง, `user_metadata.steam_id`) + upsert `profiles` → ออก session → redirect ไป `next` (ต้องอยู่ใน allow-list ของ frontend origin กัน open redirect)

**Session:** JWT ของเรา (HS256, `SESSION_SECRET`, อายุ 30 วัน, `sub` = user_id) ใน cookie `__Host-ia_session`: `HttpOnly; Secure; SameSite=Lax; Path=/` ไม่ใส่ `Domain` (host-only ของ `api.tammapol.com`)

**Same-site / CORS (เช็คแล้วตามโดเมนที่วางไว้):**
- `impactagent.tammapol.com` (Vercel) กับ `api.tammapol.com` (Tunnel) มี registrable domain เดียวกัน (`tammapol.com`) → **same-site** → cookie `SameSite=Lax` ส่งไปกับ `fetch(…, {credentials: 'include'})` ได้
- แต่เป็น **cross-origin** → API ต้องตอบ `Access-Control-Allow-Origin: https://impactagent.tammapol.com` (ค่าเป๊ะ ห้าม `*`) + `Access-Control-Allow-Credentials: true` · allow-list origin มาจาก env `FRONTEND_ORIGINS`
- CSRF: ทุก request ที่เปลี่ยนข้อมูลต้องมี header `X-IA-CSRF: 1` (ทำให้เกิด preflight ซึ่ง CORS allow-list ปิดไว้แล้ว) + เช็ค `Origin` ใน allow-list · SameSite=Lax ไม่กันจาก subdomain อื่นของ `tammapol.com` จึงต้องมีสองชั้นนี้
- Vercel preview (`*.vercel.app`) เป็น cross-site → cookie ไม่ไป → login บน preview ไม่ได้ (ทดสอบ login ที่ localhost หรือโดเมนจริง)
- Local dev: frontend `http://localhost:3000` + API `http://localhost:8000` เป็น same-site · Chrome/Firefox ถือ `localhost` เป็น secure context จึงใช้ `Secure` / `__Host-` ได้ (ถ้า browser ไหนไม่ยอม ใช้ชื่อ cookie ไม่มี prefix ผ่าน env)
- Presigned PUT ไป R2 เป็นอีก origin: ตั้ง CORS ที่ bucket (method `PUT`, origin ของ frontend, header `Content-Type`/`Content-Length`) ไม่ส่ง cookie

---

## 9. Privacy
- **แมตช์ unlisted:** ใครมีลิงก์ (`/matches/{uuid}`) ก็ดูได้ ไม่มีหน้า list/search แมตช์สาธารณะ
- **Profile:** มีเฉพาะ steam_id ที่ login แล้ว (`profiles`) · ผู้เล่นอีก 9 คนเห็นแค่ในหน้าแมตช์ (ชื่อ + สถิติของแมตช์นั้น) ไม่มีลิงก์ไป profile
- **ขอลบข้อมูล:** ต้อง login Steam เพื่อพิสูจน์ตัวตน
  - `POST /me/redact` → สร้าง `redactions` แล้ว API ซ่อนทันที (`match_players.redacted = true`: ชื่อเป็น "Player N", ไม่แสดง steam_id) → job `kind=redact` เขียนชื่อ/steam_id ใน Parquet ของแมตช์ที่เกี่ยวข้องใหม่
  - `DELETE /me` = redact + ลบ `profiles` / `auth.users` / `user_matches` ของตัวเอง (แมตช์ที่เคยอัปยังอยู่ให้คนอื่นในแมตช์)
- **Gemini free tier (beta):** Privacy Policy ต้องบอกว่าข้อความแชทและสรุปแมตช์ถูกส่งไป Google และอาจถูกใช้ปรับปรุง model · ไม่ส่ง steam_id ของคนอื่นไปใน prompt (ใช้ชื่อในแมตช์)
- ไม่เก็บข้อมูล Leetify / FACEIT ใน product (AGENTS.md)

---

## 10. โครงโฟลเดอร์และการเรียก `impactagent/`

```
impactagent/              เดิม: parse / metrics / ratings / validate (ไม่แตะ logic)
server/                   package `iaserver` (pyproject เดิม, extras [api] [worker])
  pipeline/  run.py       run_match(dem_path) -> MatchBundle (pure, ไม่ยุ่ง cloud)
             bundle.py    เขียน/อ่าน bundle (Parquet + manifest), recompute(bundle) -> derived
             versions.py  PARSE_VERSION + hash ของ registry / credit / wp_model → pipeline_version
             rows.py      bundle → แถว PG (match_players.metrics jsonb ฯลฯ)
             replay.py    (3.1b) track 8 Hz
  core/                   settings (pydantic-settings), db (psycopg pool), r2 (boto3), schemas
  api/                    main.py, routes/{auth,uploads,matches,players,privacy,meta,admin}.py, steam.py, session.py
  worker/                 main.py (claim → download → verify → run_match → store → finish), heartbeat
supabase/                 config.toml, migrations/0001_core.sql …, seed.sql
docker/                   api.Dockerfile, worker.Dockerfile
docker-compose.yml        api + worker + cloudflared (worker: mem/cpu limit, restart: always, volume ~/.awpy)
tests/server/             pipeline (bundle เทียบ data/parsed), api (TestClient + Supabase local)
.env.example              (.env อยู่ใน .gitignore)
```

`run_match` เรียก public function ของ `impactagent` ตามลำดับ: `parse_demo(path)` → `read_state_snapshots` / `build_wp_states(p)` (ครั้งเดียว) → `build_rating_events(p, states)` → `check_invariants` → `player_round_ratings` → `build_player_rounds` → `build_clutches` → `compute_match_metrics(p, events)`

Refactor ใน `impactagent/` ที่ต้องทำ (ไม่เปลี่ยน logic; `validate-all` + bundle `DataFrame.equals` ของเดิมต้องผ่าน):
1. ย้ายการแปลง dtype + `detonations` attrs จาก `_cmd_parse` ไปเป็น `write_tables()` ให้ CLI กับ pipeline ใช้ร่วมกัน
2. `compute_match_metrics(p, events=None)`: รับ rating_events ที่คำนวณแล้ว (ตอนนี้ `impact_metrics` สร้าง wp_states ใหม่ = เปิด demo ซ้ำ)
3. `read_state_snapshots(dem, ticks)` แยกจาก `_read_timers_and_equip`; `build_wp_states` รับ snapshot แทน path ได้ (§6.2)

---

## 11. Dev ในเครื่อง
- **Supabase:** dev = Supabase CLI local (`supabase start`, Docker Desktop) migration อยู่ใน `supabase/migrations/` · staging/prod = project จริง (`supabase db push`) · ทดสอบ `pg_cron`, role, RLS ในเครื่องได้
- **R2:** bucket จริงสำหรับ dev (`impactagent-dev`) เพราะ presign / CORS / lifecycle ต่างจาก MinIO · MinIO ใน compose เป็นทางเลือกสำหรับ test อัตโนมัติ
- **Secret (`.env`, gitignored; `.env.example` commit ได้):** `DATABASE_URL_API`, `DATABASE_URL_WORKER`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (API เท่านั้น), `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `SESSION_SECRET`, `STEAM_API_KEY`, `PUBLIC_API_URL`, `FRONTEND_ORIGINS`, `MAX_UPLOAD_BYTES`, `UPLOADS_PER_DAY`, `CLOUDFLARE_TUNNEL_TOKEN`, `ADMIN_WEBHOOK_URL` (ทางเลือก), `GEMINI_API_KEY` (Phase 4)
- **Library (owner ติดตั้งเอง):**

| ใช้กับ | Library |
|---|---|
| API | `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `httpx`, `pyjwt`, `psycopg[binary,pool]`, `boto3`, `duckdb` |
| Worker | `boto3`, `psycopg[binary,pool]` + `.[visibility]` (awpy) |
| Test | `pytest` |
| เครื่องมือ | Docker Desktop, Supabase CLI, `cloudflared` (image ใน compose) |
| ทีหลัง | `google-genai` (Phase 4), `hash-wasm` (frontend) |

---

## 12. แผนแบ่งช่วง
| ช่วง | งาน | ผ่านเมื่อ |
|---|---|---|
| 3.0 | doc นี้ + data-model §2.5 / §7 + roadmap | owner approve |
| 3.1 | `pipeline.run_match` + bundle ลงโฟลเดอร์ local + refactor 3 ข้อ (§10) + `state_ticks` | 5 แมตช์ bundle `equals` ไฟล์เดิมใน `data/parsed` · `validate-all` เขียว · วัดเวลา + peak RAM + ขนาดจริง |
| 3.1b | replay 8 Hz ใน bundle | ขนาด/เวลาเพิ่มวัดได้ · ตำแหน่ง ณ kill tick ใกล้ `kills.attacker_xyz` (± 1 frame) |
| 3.2 | `recompute(bundle)` ไม่มี demo | ซ่อน demo แล้ว recompute → rating_events / metrics `equals` รอบที่มี demo ทุกแมตช์ |
| 3.3 | migrations + loader (bundle → PG local) | scoreboard จาก SQL ตรงกับ `compute_match_metrics` / CLI `impact` |
| 3.4 | R2: เขียน/อ่าน bundle + manifest + lifecycle `incoming/` `failed/` | DuckDB อ่าน rating_events จาก R2 ได้ · sha ใน manifest ตรง |
| 3.5 | Worker loop (PG local + R2 dev) + `job_errors` | job เองจนจบ done · kill กลางทาง → reaper requeue · ไฟล์เสีย → failed `input` · invariant พัง (จำลอง) → failed `ours` + demo อยู่ใน `failed/` · ไฟล์ซ้ำ → duplicate |
| 3.6 | API upload flow + `upload_requests` | สคริปต์ httpx อัป demo จริง → done · 2 user อัปไฟล์เดียวกันพร้อมกัน → 1 job, ทั้งคู่ได้แมตช์ · `.dem` กับ `.dem.bz2` ของแมตช์เดียวกัน → แมตช์เดียว |
| 3.7 | Steam login + session + CORS | login ผ่าน browser ที่ localhost · `/me` ได้ steam_id · request ไม่มี CSRF header ถูกปฏิเสธ |
| 3.8 | Endpoints อ่าน match / player / privacy / admin | contract test ตรงกับ PG/Parquet · profile ของคนที่ไม่ login = 404 · redact ซ่อนชื่อ |
| 3.9 | docker-compose บน laptop (api + worker + cloudflared) | `api.tammapol.com/health` ผ่าน Tunnel · login + upload จากโดเมนจริง (same-site cookie ใช้ได้) · RAM/CPU limit, restart, heartbeat, cache mesh · อัป 5 แมตช์ติดกันผ่าน |
| 3.10 | Recompute job + `/admin/recompute` | แก้ credit.yaml ชั่วคราว → recompute ทุกแมตช์ → version ใหม่ใน R2 + PG, rollback ได้ |

## 13. ยังเปิดอยู่
- ย้ายไป VPS: เกณฑ์ (จำนวน job/วัน, เวลารอคิว) ยังไม่กำหนด
- `played_at` สำหรับ demo MM (ไม่มีวันที่ใน header): ใช้เวลาอัปไปก่อน
- Scope `CT` / `T` ใน `metrics` jsonb รอ `compute_match_metrics` คิดแยกฝั่ง
- ลบ prefix `derived/` ของ version เก่าเมื่อไหร่ (ตอนนี้ด้วยมือ)
