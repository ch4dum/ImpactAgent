"""Write / read a MatchBundle as a folder (same layout as matches/{match_id}/ in R2, backend.md §3):

  manifest.json
  events/p{N}/{table}.parquet
  snapshot/p{N}/state_ticks.parquet, defuse_starts.parquet, cvars.parquet, header.json
  derived/{pipeline_version}/{table}.parquet
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from impactagent.parse.io import parquet_ready, write_tables

from iaserver.pipeline.run import MatchBundle
from iaserver.pipeline.versions import BUNDLE_FORMAT


def _file_info(path: Path, rows: int) -> dict:
    data = path.read_bytes()
    return {"rows": rows, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


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
    for name, df in (("state_ticks", b.snapshot.state_ticks), ("defuse_starts", b.snapshot.defuse_starts),
                     ("cvars", b.snapshot.cvars)):  # cvars: thousands of rows on FACEIT servers
        parquet_ready(df).to_parquet(sn_dir / f"{name}.parquet", index=False)
        files[f"{name}.parquet"] = _file_info(sn_dir / f"{name}.parquet", len(df))
    header = {"map": b.map_name, "tickrate": b.tickrate, "client_build": b.client_build,
              "header": {k: str(v) for k, v in b.snapshot.header.items()}}
    (sn_dir / "header.json").write_text(json.dumps(header, ensure_ascii=False, indent=1), encoding="utf-8")
    files["header.json"] = _file_info(sn_dir / "header.json", 1)
    layers["snapshot"] = {"prefix": f"snapshot/{pv}", "files": files}

    dv_dir = out / "derived" / b.pipeline_version
    dv_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, df in b.derived.items():
        df.to_parquet(dv_dir / f"{name}.parquet", index=False)
        files[f"{name}.parquet"] = _file_info(dv_dir / f"{name}.parquet", len(df))
    layers["derived"] = {"prefix": f"derived/{b.pipeline_version}", "files": files}

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
        "timings_s": {k: round(v, 3) for k, v in b.timings.items()},
        "warnings": b.warnings,
        "wp_stats": {k: v for k, v in b.wp_stats.items() if k != "timer_warns"},
        "checks": {"invariants": "OK"},  # run_match raises InvariantError otherwise
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
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
                tables[fname.removesuffix(".parquet")] = pd.read_parquet(f)
            else:
                tables[fname] = json.loads(f.read_text(encoding="utf-8"))
        out[layer] = tables
    return out
