# ImpactAgent v2

CS2 demo analytics platform (Leetify-style stats) with an LLM coach you can chat with about your matches.

> Clean rebuild. The original prototype lives on the `main` branch as a reference draft only — nothing is carried over.

## Status

Phase 0 — **Metric spec.** Reverse-engineering what each Leetify stat means and how to compute it from a `.dem`, before writing any parser code.

- [`docs/metrics/leetify-metrics-spec.md`](docs/metrics/leetify-metrics-spec.md) — metric-by-metric definitions, required demo data, open questions

## Planned architecture (not built yet)

```
Browser ──presigned upload──▶ Object storage (R2)
   │                              │
   ▼                              ▼
FastAPI  ──enqueue──▶  Parse worker (demoparser2) ──▶ Postgres (matches, rounds, kills, stats)
   │                                                     ▲
   └──── LLM coach (LangGraph agent, tool calls / read-only SQL) ─┘
```
