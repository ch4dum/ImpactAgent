"""Write a ParsedDemo's tables to Parquet (shared by the `parse` CLI and server/iaserver)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def parsed_tables(p) -> dict[str, pd.DataFrame]:
    """p.tables() plus `detonations` (kept in grenades.attrs) when the demo has any."""
    tables = p.tables()
    det = p.grenades.attrs.get("detonations")
    if det is not None and not det.empty:
        tables["detonations"] = det
    return tables


def parquet_ready(df: pd.DataFrame) -> pd.DataFrame:
    """Copy without attrs; lists (inventory) stay Parquet lists, other object columns -> string."""
    df = df.copy()
    df.attrs = {}
    for c in df.columns:
        if df[c].dtype == object and not df[c].map(lambda v: isinstance(v, (list, type(None)))).all():
            df[c] = df[c].astype("string")
    return df


def write_tables(tables: dict[str, pd.DataFrame], out_dir: str | Path) -> dict[str, int]:
    """Write each table to <out_dir>/<name>.parquet. -> {name: rows}."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    for name, df in tables.items():
        parquet_ready(df).to_parquet(out / f"{name}.parquet", index=False)
        rows[name] = len(df)
    return rows
