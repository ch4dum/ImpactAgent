"""Player state at a set of ticks, read from the demo only for the ticks a query needs.

Nothing here is stored (data-model §1: no tick data); callers sample, decide, and drop it.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

DUCK_VIEW_OFFSET = "CCSPlayerPawn.CCSPlayer_MovementServices.m_flDuckViewOffset"
BASE_PROPS = ["X", "Y", "Z", DUCK_VIEW_OFFSET, "pitch", "yaw", "is_alive"]
SPOTTED_PROP = "approximate_spotted_by"


class TickStates:
    """(tick, steam_id) -> player state. Missing players / ticks return None."""

    def __init__(self, df: pd.DataFrame):
        sid = df["steamid"].astype("string")
        self._pos = {}
        cols = [df["tick"].astype(int), sid, df["X"], df["Y"], df["Z"],
                df[DUCK_VIEW_OFFSET].fillna(0.0) if DUCK_VIEW_OFFSET in df else pd.Series(0.0, index=df.index),
                df["pitch"], df["yaw"], df["is_alive"]]
        for t, s, x, y, z, dvo, pitch, yaw, alive in zip(*cols):
            if x is None or np.isnan(x):
                continue
            self._pos[(t, s)] = (float(x), float(y), float(z), float(dvo), float(pitch), float(yaw), bool(alive))
        self._spotted = {}
        if SPOTTED_PROP in df:
            for t, s, v in zip(df["tick"].astype(int), sid, df[SPOTTED_PROP]):
                self._spotted[(t, s)] = {str(x) for x in v} if v is not None and not isinstance(v, float) else set()

    @classmethod
    def load(cls, parser, ticks: Iterable[int], spotted: bool = False) -> TickStates:
        ticks = sorted({int(t) for t in ticks if t >= 0})
        props = BASE_PROPS + ([SPOTTED_PROP] if spotted else [])
        if not ticks:
            return cls(pd.DataFrame(columns=["tick", "steamid", *props]))
        return cls(pd.DataFrame(parser.parse_ticks(props, ticks=ticks)))

    def get(self, tick: int, sid: str):
        """(x, y, z, duck_view_offset, pitch, yaw, is_alive) or None."""
        return self._pos.get((tick, sid))

    def spotted_by(self, tick: int, sid: str) -> set[str] | None:
        return self._spotted.get((tick, sid))

    def __len__(self) -> int:
        return len(self._pos)
