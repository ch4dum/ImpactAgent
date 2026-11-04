# AGENTS.md — ImpactAgent v2

CS2 demo (`.dem`) analytics web app in the style of Leetify, plus an LLM coach that users can chat with about their matches. Owner: Tammapol (ch4dum), junior AI engineer (LLM agents, RAG, NL2SQL, Python/FastAPI/LangGraph). He writes in Thai; reply in Thai, keep code, identifiers and commit messages in English.

## Branches
- `v2` (this branch): **clean rebuild**, orphan branch. All new work goes here.
- `main`: the old prototype. Reference only, never merge or copy code from it wholesale.

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
| `impactagent/metrics/compute.py` | General + Utility metrics per player, `compute_match_metrics(parsed)` |
| `impactagent/__main__.py` | CLI: `inspect`, `parse`, `validate` |
| `impactagent/validate/__init__.py` | Compare our metrics with a truth JSON; aborts if demo and truth look like different matches |
| `data/validation/inferno-44a522c3.json` | **Validation pair 1 (calibration):** Leetify's real values for `scripts/demos/003852158461294936246_0991785667.dem.bz2` (de_inferno 13:0, 13 rounds; utility only for our team; read its `note`). **Gitignored, never commit.** |
| `data/validation/mirage-65db631a.json` | **Validation pair 2 (holdout):** `scripts/demos/003850878442929127864_1489073941.dem.bz2` (de_mirage 13:11, 24 rounds; utility for both teams, some nulls; players may carry `aliases`). Gitignored. |
| `data/validation/dust2-f2633f5c.json` | Leetify values for a de_dust2 13:9 match. **No local demo matches it** (`dust2win.dem`, `dust139.dem`, `dust1614.dem` are other matches). Don't tune anything to it. Gitignored. |
| `data/parsed/` | Parser outputs (Parquet). Gitignored. |

## Current status (2026-11-05)
Phase 0 (research) and data model v0.1 are done. CLI (`inspect`, `parse`, `validate`, `validate-all`) is done. **Core metrics (General + Utility + trade succeeded + opening traded %) match Leetify on both pairs: inferno 275/275, mirage 320/320** (player × metric); opening duels 37/37 rounds; clutches 43/43. Trade opportunity / attempt are hypotheses (~60% exact), reported as `calibrating` (not gating). Which rules are proven by 2 matches, 1 match, or still hypotheses: `docs/metrics/leetify-metrics-spec.md` §8.

Validate (run after every metric/parser change; all pairs must stay green):
```
python -m impactagent validate-all
```

### Next steps
1. Next Phase 1 items in `docs/roadmap.md`: metric registry YAML (`impactagent/metrics/registry.yaml`, fields in data-model §4), then visibility → Aim, then re-calibrate trade opportunity / attempt with real visibility.
2. Hypotheses in spec §8 (🟡) need a match that separates them, e.g. a kill during a ≤ 1.1s blind, capped molotov / team-HE hits.

## Rules
- **Roadmap:** update `docs/roadmap.md` (tick checklist items, add new decisions) every time a piece of work is finished or a new decision is made.
- **Commits:** the owner commits himself (GitHub Desktop). When work is ready, propose a message: **Summary ≤ 5 words**, details as bullet points in the **Description**. Don't commit or push unless asked.
- **Leetify data:** validation values copied from Leetify stay in gitignored `data/validation/`. Don't store Leetify API data in the product, don't scrape Leetify, and stop if a site shows a bot check. Our metric names must be our own, not Leetify's (their API guidelines forbid reusing their names/recalculating their scores under their name).
- **Trademark:** no "CS2"/"Counter-Strike" in the product or domain name.
- Keep raw tick data out of storage; follow the event-based model in `docs/design/data-model.md`. If the code needs a model change, update that doc in the same change.
- Never average percentages across matches; aggregate numerator/denominator (data-model §1).
