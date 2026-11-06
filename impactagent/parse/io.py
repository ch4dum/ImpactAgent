"""Write / read a ParsedDemo's tables as Parquet (shared by the `parse` CLI and server/iaserver).

Round-trip (write -> read_table) gives back an equal DataFrame, except object columns that
hold only strings: they come back as a string dtype with the same values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def parsed_tables(p) -> dict[str, pd.DataFrame]:
    """p.tables() plus `detonations` (kept in grenades.attrs) when the demo has any."""
    tables = p.tables()
    det = p.grenades.attrs.get("detonations")
    if det is not None and not det.empty:
        tables["detonations"] = det
    return tables


def _is_null(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def _bool_or_null(s: pd.Series) -> bool:
    """True if every non-null value of an object column is a bool (Python bool or np.bool_)."""
    return all(_is_null(v) or isinstance(v, (bool, np.bool_)) for v in s)


def parquet_ready(df: pd.DataFrame) -> pd.DataFrame:
    """Copy without attrs, ready for to_parquet.

    Object columns: lists (inventory) and bool + None (e.g. has_defuser of a player with no
    pawn) stay as they are — Parquet stores them as list / nullable bool and read_table gives
    them back; anything else (strings, mixed types) -> pandas string.
    """
    df = df.copy()
    df.attrs = {}
    for c in df.columns:
        if df[c].dtype != object:
            continue
        if df[c].map(lambda v: isinstance(v, (list, type(None)))).all():
            continue
        if _bool_or_null(df[c]):
            continue
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


def read_table(path: str | Path) -> pd.DataFrame:
    """read_parquet + list columns back to Python lists (Parquet gives numpy arrays)."""
    df = pd.read_parquet(path)
    for c in df.columns:
        if df[c].dtype == object and df[c].map(lambda v: isinstance(v, np.ndarray)).any():
            df[c] = df[c].map(lambda v: v.tolist() if isinstance(v, np.ndarray) else v)
    return df
