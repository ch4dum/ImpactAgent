# AGENTS.md — ImpactAgent

CS2 demo (`.dem`) analytics web app in the style of Leetify, plus an LLM coach that users can chat with about their matches. Owner: Tammapol (ch4dum), junior AI engineer (LLM agents, RAG, NL2SQL, Python/FastAPI/LangGraph). He writes in Thai; reply in Thai, keep code, identifiers and commit messages in English.

## Language (สำคัญมาก)
- ตอบผู้ใช้เป็น **ภาษาไทยเท่านั้น** ทุกข้อความ รวมถึงข้อความสั้นๆ ระหว่างทำงาน สรุป และคำถาม ใช้ศัพท์เทคนิคภาษาอังกฤษปนได้ (เช่น holdout, registry, tick) แต่ห้ามใช้ภาษาเวียดนาม จีน หรือภาษาอื่น
- Always write to the user in Thai, including short progress notes between tool calls. Never Vietnamese, Chinese or any other language. Code, identifiers and commit messages stay in English.

## Branches
- `main` (this branch, GitHub default): the **clean rebuild** (was `v2`, renamed 2026-11-05). All new work goes here.
- `v1-draft`: the old prototype (was `main`). Unrelated history. Reference only, never merge or copy code from it wholesale.
- Don't delete branches without asking the owner.

## Environment (Windows)
- Conda env **`ImpactAgent`** at `C:\Users\tamma\miniconda3\envs\ImpactAgent`
- Setup / refresh:
  ```
  conda activate ImpactAgent
  pip install -e .
  ```
- `conda` may not be on PATH in tool shells; call `C:\Users\tamma\miniconda3\envs\ImpactAgent\python.exe` directly.
- Demo files (~80-330 MB each, gitignored: `*.dem`, `*.dem.bz2`, `*.dem.gz`, `*.dem.zst`) live in `scripts/demos/` (in the repo folder, ignored) and older ones in `..\scripts\demos\`. Never commit demos. `parse_demo` reads `.dem`, `.dem.bz2`, `.dem.gz` (and `.dem.zst` if `zstandard` is installed).
- Only open the demo paired with a truth file; to identify an unknown demo, check header + `round_end` + player names only, one file at a time.

## Repo map
| Path | What |
|---|---|
| `docs/metrics/leetify-metrics-spec.md` | How each Leetify metric is defined/computed, open questions, validation plan |
| `docs/metrics/parameters.md` | Every Leetify parameter by category: meaning, API field, unit, direction, example, status |
| `docs/research/leetify-sitemap.md` | Leetify site structure page by page, and takeaways for ImpactAgent |
| `docs/roadmap.md` | Phases, checklist, decisions. Keep it current. |
| `docs/design/data-model.md` | **Data model v0.1**: tables, page→table mapping, metric registry fields, pipeline. Code must follow this. |
| `impactagent/constants.py` | Game constants (team nums, grenade prices, blind threshold, trade window) |
| `impactagent/parse/demo.py` | `parse_demo(path) -> ParsedDemo` (event tables via demoparser2) |
| `impactagent/metrics/compute.py` | Metrics per player (general, utility, trades, clutches), `compute_match_metrics(parsed)` |
| `impactagent/metrics/registry.yaml` | **Metric registry**: one entry per finished metric (data-model §4), `status: exact` / `calibrating`. Add a metric here when it is done; validate reads `calibrating` from it |
| `impactagent/parse/aim.py` | Shot features (`aim_shot`, hit, head, enemy_spotted, spray, first bullet) and `engagements` (first seen → damage / kill), built in `parse_demo` with the raycast backend (spotted fallback without awpy) |
| `impactagent/metrics/aim.py` | Aim metrics (`aim_metrics`), joined into `compute_match_metrics` |
| `impactagent/parse/trades.py` | `trade_windows` (per death × alive teammate, features sampled inside the trade window) |
| `impactagent/visibility/` | Visibility module: `SpottedBackend` (game) / `RaycastBackend` (awpy mesh, lag window, smoke spheres, FOV) behind one `sees()` interface; `report.py` = kill visibility report (`python -m impactagent visibility DEMO...`). Raycast needs `pip install -e .[visibility]` |
| `impactagent/__main__.py` | CLI: `inspect`, `parse`, `validate`, `validate-all`, `visibility` |
| `impactagent/validate/known_exceptions.yaml` | Single cells with no known cause yet (status `known`, not gating) |
| `impactagent/validate/__init__.py` | Compare our metrics with a truth JSON; aborts if demo and truth look like different matches |
| `data/validation/inferno-44a522c3.json` | **Validation pair 1 (calibration):** Leetify's real values for `scripts/demos/003852158461294936246_0991785667.dem.bz2` (de_inferno 13:0, 13 rounds; utility only for our team; read its `note`). **Gitignored, never commit.** |
| `data/validation/mirage-65db631a.json` | **Validation pair 2 (holdout):** `scripts/demos/003850878442929127864_1489073941.dem.bz2` (de_mirage 13:11, 24 rounds; utility for both teams, some nulls; players may carry `aliases`). Gitignored. |
| `data/validation/dust2-85507dfb.json` | **Validation pair 3 (holdout):** `scripts/demos/003849547149096255807_0663000482.dem.bz2` (de_dust2 13:7, 20 rounds; non-ASCII names; ch4dum on SSG08). Gitignored. Holdout result (code before any change): core 353/360, opening 20/20, clutch 25/25 (spec §6) |
| `data/validation/dust2-f2633f5c.json` | Leetify values for a de_dust2 13:9 match. **No local demo matches it** (`dust2win.dem`, `dust139.dem`, `dust1614.dem` are other matches). Don't tune anything to it. Gitignored. |
| `data/parsed/` | Parser outputs (Parquet). Gitignored. |

## Current status (2026-11-05)
Phase 0 (research) and data model v0.1 are done. Full plan and checklist: `docs/roadmap.md`.

- **CLI:** `inspect`, `parse`, `validate`, `validate-all`, `visibility`. `parse_demo` reads `.dem` / `.dem.bz2` / `.dem.gz` (`.dem.zst` with zstandard), caps the decompressed demo at 1 GiB and parses in a child process killed after 300 s (`MAX_DEMO_BYTES`, `PARSE_TIMEOUT_SECONDS` in `constants.py`).
- **Metrics vs Leetify:** core (General + Utility + trade succeeded + opening traded % + shots fired / accuracy / head accuracy) **inferno 305/305, mirage 350/350** (player × metric); opening duels 37/37 rounds; clutches 43/43 (incl. disconnect deaths). Trade opportunity / attempt and 7 Aim metrics (spotted accuracy, spray, counter-strafe, first bullet, TTD, TTK, crosshair) are `calibrating`, not gating. Rule-by-rule evidence (2 matches / 1 match / hypothesis): `docs/metrics/leetify-metrics-spec.md` §8.
- **Dust2 holdout (pair 3):** core 356/356 + 4 known exceptions (unused utility ×3, blind duration yyh; cause unknown, `impactagent/validate/known_exceptions.yaml`, spec §8). Inferno 305/305, Mirage 350/350; `validate-all` passes.
- **Known exceptions:** one entry per (pair, player, metric) with a reason, never a tolerance; validate prints them and warns STALE when a cell matches again.
- **Visibility:** `impactagent/visibility/` (raycast default, 8 target points `TARGET_LAYOUT`, spotted switchable): normal kills seen inferno 72/72, mirage 150/152; lag window fixed 7 ticks (ping does not explain the rewind); smoke spheres R 144 / +32z / 0.5 s bloom; FOV 50°. Spec §0 + §8.
- **Metric registry:** `impactagent/metrics/registry.yaml`, 53 metrics (42 exact, 11 calibrating). Every finished metric gets an entry; `validate-all` checks it and reads `calibrating` from it.
- **Branches:** v2 became `main` and the old `main` became `v1-draft` (2026-11-05); main's history was rewritten the same day.

Validate (run after every metric/parser change; all pairs and the registry must stay green):
```
python -m impactagent validate-all
```

### Next steps (Phase 1 in `docs/roadmap.md`)
1. Trade opportunity / attempt: visibility-based definitions did not generalize (raycast 23/40 inferno, 11/40 mirage holdout vs current 22/40, 25/40); kept the current one. Needs per-death truth (spec §3).
2. Aim calibrating metrics: our TTD / crosshair are below Leetify for every player (we see enemies later). 8 target points cut the TTD bias from -173 / -143 to -125 / -83 ms (spec §1); try a bigger hitbox before changing the default. Crosshair barely moves, so its definition differs. Spray accuracy is probably not hits/shots.
3. Round buy type + Map Zones.
4. Hypotheses in spec §8 (🟡) need a match that separates them, e.g. a kill during a ≤ 1.1s blind, capped molotov / team-HE hits. A new truth file is a holdout: run `validate-all` before changing code.

## Rules
- **Roadmap:** update `docs/roadmap.md` (tick checklist items, add new decisions) every time a piece of work is finished or a new decision is made.
- **Commits:** the owner commits himself (GitHub Desktop). When work is ready, propose a message: **Summary ≤ 5 words**, details as bullet points in the **Description**. Don't commit or push unless asked. No AI co-author / session trailers in commit messages or PRs, and no notes in the repo saying which AI tool wrote something.
- **Leetify data:** validation values copied from Leetify stay in gitignored `data/validation/`. Don't store Leetify API data in the product, don't scrape Leetify, and stop if a site shows a bot check. Our metric names must be our own, not Leetify's (their API guidelines forbid reusing their names/recalculating their scores under their name).
- **Trademark:** no "CS2"/"Counter-Strike" in the product or domain name.
- Keep raw tick data out of storage; follow the event-based model in `docs/design/data-model.md`. If the code needs a model change, update that doc in the same change.
- Never average percentages across matches; aggregate numerator/denominator (data-model §1).
