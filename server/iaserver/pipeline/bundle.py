"""Write / read / recompute a MatchBundle as a folder (same layout as matches/{dem_sha256}/ in R2,
backend.md §3):

  manifest.json
  events/p{N}/{table}.parquet
  snapshot/p{N}/state_ticks.parquet, defuse_starts.parquet, cvars.parquet, header.json
  derived/{pipeline_version}/{table}.parquet

Parquet `match_id` (wp_states, rating_events, …) = dem_sha256, the permanent key of a match
outside Postgres (owner 2026-11-06).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pandas as pd

from impactagent.parse.demo import ParsedDemo
from impactagent.parse.io import parquet_ready, read_table, write_tables
from impactagent.ratings.wp_states import StateSnapshot

from iaserver.pipeline.run import MatchBundle, derive
from iaserver.pipeline.versions import BUNDLE_FORMAT, components, pipeline_version

SNAPSHOT_TABLES = ("state_ticks", "defuse_starts", "cvars")
NO_DEMO = Path("<no demo>")


def _file_info(path: Path, rows: int) -> dict:
    data = path.read_bytes()
    return {"rows": rows, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _write_derived(out: Path, pv: str, derived: dict[str, pd.DataFrame]) -> dict:
    """Plain to_parquet (same as the CLI `impact` files in data/parsed)."""
    dv_dir = out / "derived" / pv
    dv_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, df in derived.items():
        df.to_parquet(dv_dir / f"{name}.parquet", index=False)
        files[f"{name}.parquet"] = _file_info(dv_dir / f"{name}.parquet", len(df))
    return {"prefix": f"derived/{pv}", "files": files}


def write_bundle(b: MatchBundle, out_dir: str | Path) -> dict:
    """-> manifest (also written to <out_dir>/manifest.json)."""
    out = Path(out_dir)
    pv = b.versions["parse_version"]
    layers: dict[str, dict] = {}

    ev_dir = out / "events" / pv
    rows = write_tables(b.events, ev_dir)
    layers["events"] = {"prefix": f"events/{pv}",
                        "files": {f"{n}.parquet": _file_info(ev_dir / f"{n}.parquet", r) for n, r in rows.items()}}

    sn_dir = out / "snapshot" / pv
    sn_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in SNAPSHOT_TABLES:  # cvars: thousands of rows on FACEIT servers
        df = getattr(b.snapshot, name)
        parquet_ready(df).to_parquet(sn_dir / f"{name}.parquet", index=False)
        files[f"{name}.parquet"] = _file_info(sn_dir / f"{name}.parquet", len(df))
    header = {"map": b.map_name, "tickrate": b.tickrate, "client_build": b.client_build,
              "match_end_tick": None if b.match_end_tick is None else int(b.match_end_tick),
              "visibility_backend": b.visibility_backend, "parse_warnings": b.parse_warnings,
              "header": {k: str(v) for k, v in b.snapshot.header.items()}}
    _write_json(sn_dir / "header.json", header)
    files["header.json"] = _file_info(sn_dir / "header.json", 1)
    layers["snapshot"] = {"prefix": f"snapshot/{pv}", "files": files}

    layers["derived"] = _write_derived(out, b.pipeline_version, b.derived)

    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "source_name": b.source.name,
        "dem_sha256": b.sha256,
        "map": b.map_name,
        "tickrate": b.tickrate,
        "client_build": b.client_build,
        "rounds_played": b.rounds_played,
        "pipeline_version": b.pipeline_version,
        "versions": b.versions,
        "layers": layers,
        "derived_history": [],
        "timings_s": {k: round(v, 3) for k, v in b.timings.items()},
        "warnings": b.warnings,
        "wp_stats": {k: v for k, v in b.wp_stats.items() if k != "timer_warns"},
        "checks": {"invariants": "OK"},  # derive raises InvariantError otherwise
        "created_at": _now(),
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


def read_bundle(bundle_dir: str | Path) -> dict:
    """-> {"manifest", "events": {table: df}, "snapshot": {...}, "derived": {table: df}}."""
    d = Path(bundle_dir)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    out: dict = {"manifest": manifest}
    for layer, info in manifest["layers"].items():
        tables = {}
        for fname in info["files"]:
            f = d / info["prefix"] / fname
            if fname.endswith(".parquet"):
                tables[fname.removesuffix(".parquet")] = read_table(f)
            else:
                tables[fname] = json.loads(f.read_text(encoding="utf-8"))
        out[layer] = tables
    return out


def load_inputs(bundle_dir: str | Path) -> tuple[ParsedDemo, StateSnapshot, dict]:
    """Rebuild the ParsedDemo + StateSnapshot of a bundle (events/ + snapshot/), without the demo.
    `path` points nowhere: any code that tries to open the demo fails."""
    b = read_bundle(bundle_dir)
    m, ev, sn = b["manifest"], b["events"], b["snapshot"]
    hdr = sn["header.json"]
    rounds = ev["rounds"]
    if hdr.get("match_end_tick") is not None:
        rounds.attrs["match_end_tick"] = hdr["match_end_tick"]
    grenades = ev["grenades"]
    if "detonations" in ev:
        grenades.attrs["detonations"] = ev["detonations"]
    p = ParsedDemo(
        path=NO_DEMO / m["source_name"], sha256=m["dem_sha256"], map_name=m["map"], tickrate=m["tickrate"],
        rounds=rounds, players=ev["players"], player_rounds_side=ev["player_rounds_side"], kills=ev["kills"],
        damages=ev["damages"], shots=ev["shots"], grenades=grenades, blinds=ev["blinds"], bomb=ev["bomb"],
        death_inventory=ev["death_inventory"], trade_windows=ev["trade_windows"], smokes=ev["smokes"],
        engagements=ev["engagements"], player_zones=ev["player_zones"],
        visibility_backend=hdr.get("visibility_backend", ""), client_build=m["client_build"],
        warnings=list(hdr.get("parse_warnings", [])),
    )
    snap = StateSnapshot(state_ticks=sn["state_ticks"], defuse_starts=sn["defuse_starts"],
                         cvars=sn["cvars"], header=hdr.get("header", {}))
    return p, snap, m


def recompute(bundle_dir: str | Path) -> dict:
    """events/ + snapshot/ -> new derived/{pipeline_version}/ with the current metric / WP /
    credit code. Older derived/ prefixes are kept (listed in manifest `derived_history`).
    -> updated manifest. Raises InvariantError (manifest untouched)."""
    d = Path(bundle_dir)
    t0 = time.perf_counter()
    p, snap, m = load_inputs(d)
    t_load = time.perf_counter() - t0
    derived, wp_stats, t = derive(p, snap)
    comps = components(parse_version=m["versions"]["parse_version"])
    pv = pipeline_version(comps)
    layer = _write_derived(d, pv, derived)
    old = m["layers"]["derived"]
    if old["prefix"] != layer["prefix"]:
        m["derived_history"] = [h for h in m.get("derived_history", []) if h["prefix"] != layer["prefix"]]
        m["derived_history"].append({"prefix": old["prefix"], "pipeline_version": m["pipeline_version"],
                                     "versions": m["versions"]})
    m["layers"]["derived"] = layer
    m["pipeline_version"] = pv
    m["versions"] = comps
    m["wp_stats"] = {k: v for k, v in wp_stats.items() if k != "timer_warns"}
    m["recompute_timings_s"] = {"load": round(t_load, 3), **{k: round(v, 3) for k, v in t.items()}}
    m["checks"] = {"invariants": "OK"}
    m["recomputed_at"] = _now()
    _write_json(d / "manifest.json", m)
    return m
