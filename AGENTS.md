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
- Demo files live **outside the repo** in `..\scripts\demos\` (e.g. `..\scripts\demos\dust2win.dem`, ~180 MB each). Never copy demos into the repo.

## Repo map
| Path | What |
|---|---|
| `docs/metrics/leetify-metrics-spec.md` | How each Leetify metric is defined/computed, open questions, validation plan |
| `docs/metrics/parameters.md` | Every Leetify parameter by category: meaning, API field, unit, direction, example, status |
| `docs/research/leetify-sitemap.md` | Leetify site structure page by page, and takeaways for ImpactAgent |
| `docs/design/data-model.md` | **Data model v0.1**: tables, page→table mapping, metric registry fields, pipeline. Code must follow this. |
| `impactagent/constants.py` | Game constants (team nums, grenade prices, blind threshold, trade window) |
| `impactagent/parse/demo.py` | `parse_demo(path) -> ParsedDemo` (event tables via demoparser2) |
| `impactagent/metrics/compute.py` | General + Utility metrics per player, `compute_match_metrics(parsed)` |
| `data/validation/dust2-f2633f5c.json` | Leetify's real values for `dust2win.dem` (all 10 players). **Gitignored, never commit.** |
| `data/parsed/` | Parser outputs (Parquet). Gitignored. |

## Current status (2026-11-05)
Phase 0 (research) and data model v0.1 are done. Parser + General/Utility metrics are **written but never run** (demoparser2 column names were written from memory and may be wrong).

### Next steps
1. `pip install -e .` in the `ImpactAgent` env.
2. Add a CLI (`impactagent/__main__.py`):
   - `python -m impactagent inspect <demo>`: list game events and the columns of `player_death`, `player_hurt`, `weapon_fire`, `player_blind`, `round_end`, and `parse_ticks(["inventory"])`, so column names can be checked.
   - `python -m impactagent parse <demo> [--out data/parsed/<stem>]`: write each table to Parquet.
   - `python -m impactagent validate <demo> --truth data/validation/dust2-f2633f5c.json`: compare our metrics with Leetify's per player per metric, print a table with diff and % diff.
3. Run `inspect` first and fix `parse/demo.py` to the real column names.
4. Run `validate` and iterate until General + Utility match:
   - Target: exact for counts (kills, deaths, assists, multi-kills, grenades thrown); within ~2-3% for ratios.
   - Known unknowns to calibrate: trade window (`TRADE_WINDOW_SECONDS`, KAST depends on it), how Leetify counts flashes thrown, unused-utility prices (incendiary price), whether flash assists need `> 1.1s` blind.
   - Record every finding (what Leetify actually does) back into `docs/metrics/leetify-metrics-spec.md`.
5. Then: metric registry YAML (`impactagent/metrics/registry.yaml`, fields in data-model §4), trades (`trade_windows`), opening duels, clutches. Aim metrics need the visibility module (spec §0) and come after.

## Rules
- **Commits:** the owner commits himself (GitHub Desktop). When work is ready, propose a message: **Summary ≤ 5 words**, details as bullet points in the **Description**. Don't commit or push unless asked.
- **Leetify data:** validation values copied from Leetify stay in gitignored `data/validation/`. Don't store Leetify API data in the product, don't scrape Leetify, and stop if a site shows a bot check. Our metric names must be our own, not Leetify's (their API guidelines forbid reusing their names/recalculating their scores under their name).
- **Trademark:** no "CS2"/"Counter-Strike" in the product or domain name.
- Keep raw tick data out of storage; follow the event-based model in `docs/design/data-model.md`. If the code needs a model change, update that doc in the same change.
- Never average percentages across matches; aggregate numerator/denominator (data-model §1).
