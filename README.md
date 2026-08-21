# 🚀 ImpactAgent: CS2 Replay (.dem) to LLM Knowledge Base Generator

**ImpactAgent** is a 100% standalone, offline Python engine that converts Counter-Strike 2 replay files (`.dem`) into structured, deep **Markdown Knowledge Base (`.md`)** files using `demoparser2`.

The generated Knowledge Base payload is optimized specifically for Large Language Models (LLMs) such as **ChatGPT, Claude, and Gemini** to serve as an interactive, pro-level **CS2 Tactical AI Coach** without relying on external web APIs or third-party cloud services.

---

## ✨ Key Features

- 🔒 **100% Standalone & Offline:** Zero external web API calls, zero API keys required. All spatial and event processing runs locally using `demoparser2`.
- 🛡️ **Warmup & Knife Round Filtering:** Automatically detects the official match start tick (`round_announce_match_start`), filters out warmup/knife rounds, and indexes official match rounds (Match Round 1 to 24+).
- 🎯 **Rifle Counter-Strafe Accuracy:** Calculates counter-strafe stopping accuracy specifically on rifles/snipers (AK47, M4A1-S, AWP, etc.) to eliminate run-and-gun noise from SMGs and pistols.
- ⏱️ **Dynamic Spray-Start Time-To-Damage (TTD):** Measures reaction and engagement latency (ms) from the first shot of a spray sequence to the first damage dealt.
- 📐 **3D Crosshair Preaim Error (°):** Calculates 3D crosshair placement error in degrees relative to enemy head coordinates upon initial duel visibility.
- 📍 **Multi-Phase Territory Control Snapshots:** Samples player positions at $t=15\text{s}$ (early setup) and $t=45\text{s}$ (mid-round regroup) for every round.
- 💥 **Utility Effective Damage & Flashbang Matrix:** Aggregates HE grenade and molotov damage by callout zone, along with flashbang enemy blind durations and teammate blind warnings.
- ⚔️ **Trade Frag Efficiency:** Calculates traded death percentages, failed early pushes ($t \le 20\text{s}$ untraded deaths), and individual trade kill conversion percentages.

---

## 📂 10 Structured Knowledge Base Sections

1. **🗺️ 1. Team Macro, Site Executions & Plant Summary** — Bomb plant distribution across A-Site and B-Site.
2. **⚔️ 2. First Kill / First Death & Trade Frag Efficiency** — FK, FD, Failed Early Pushes, Traded Death %, and Trade Kill Conversion %.
3. **📊 3. Overall Performance & Ratings Summary** — Combat ratings, K/D, ADR, Headshots, and Survived Rounds.
4. **🎯 4. Precision Mechanics & Aim Accuracy** — Preaim Error (°), Reaction TTD (ms), and Rifle Counter-Strafe Acc %.
5. **🔫 5. Per-Weapon Micro-Mechanics Breakdown** — Velocity at firing and accurate vs. moving shots per weapon.
6. **📍 6. Multi-Phase Territory Control Snapshots** — 10-player location telemetry at $t=15\text{s}$ and $t=45\text{s}$.
7. **💥 7. HE Grenade & Molotov Effective Damage** — Total utility damage dealt categorized by callout location.
8. **💣 8. Flashbang Efficiency Matrix** — Enemy blind durations and teammate blind warnings per player.
9. **🚪 9. Spatial Opening Duels Log** — Opening engagement log with T/CT side tags, callouts, preaim error, and trade status.
10. **💀 10. Chronological Micro-Telemetry Kill Log** — Tick-by-tick kill log containing TTD ms, preaim error, attacker speed, and trade status.

---

## 🛠️ Installation

### 1. Prerequisites
- **Python 3.9** or higher

### 2. Install Dependencies
Open your terminal or command prompt in the repository folder and run:

```bash
pip install -r requirements.txt
```

---

## 🚀 How to Run & Use

### 1. Generate Knowledge Base (.md) from a CS2 Replay (.dem)

Place your `.dem` replay file in `scripts/demos/` or pass the path directly:

```bash
python main.py --demo scripts/demos/your_match.dem
```

To specify a custom output path:

```bash
python main.py --demo path/to/match.dem --output data/custom_kb.md
```

The output file will be saved at **`data/<match_name>_kb.md`**.

---

### 💬 2. Feeding the Output to an LLM (ChatGPT / Claude / Gemini)

1. Open the generated **`data/<match_name>_kb.md`** file and copy its contents.
2. Paste the content into **ChatGPT, Claude, or Gemini** alongside a prompt such as:

> *"You are an expert CS2 Tactical AI Coach. Analyze the following match Knowledge Base file and provide a comprehensive performance report for player [Player Name], covering micro-mechanics (preaim, counter-strafing, TTD), macro positioning, utility efficiency, and tactical recommendations."*

---

## 📄 License
MIT License
