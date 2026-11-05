"""Smokes as spheres in time: [detonate + bloom, expired]. CS2 HE holes in smoke are ignored."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from impactagent.constants import (
    SMOKE_BLOOM_SECONDS,
    SMOKE_CENTER_Z_OFFSET,
    SMOKE_DURATION_SECONDS,
    SMOKE_RADIUS,
)
from impactagent.visibility.geometry import Vec, segment_sphere

SMOKE_COLUMNS = ["round_no", "entity_id", "thrower_id", "detonate_tick", "expire_tick", "x", "y", "z"]


def pair_smokes(det: pd.DataFrame, exp: pd.DataFrame, tickrate: int) -> pd.DataFrame:
    """One row per smoke. Entity ids are reused, so each detonation takes the first expiry of the
    same entity after it (within duration + 1 s); missing = detonate + duration (round ended)."""
    if det.empty:
        return pd.DataFrame(columns=SMOKE_COLUMNS)
    dur = int(round(SMOKE_DURATION_SECONDS * tickrate))
    exp_by = {e: np.sort(g["tick"].to_numpy()) for e, g in exp.groupby("entity_id")} if not exp.empty else {}
    out = det.copy()
    ends = []
    for e, t in zip(out["entity_id"], out["detonate_tick"]):
        arr = exp_by.get(e)
        end = None
        if arr is not None:
            i = np.searchsorted(arr, t, side="right")
            if i < len(arr) and arr[i] - t <= dur + tickrate:
                end = int(arr[i])
        ends.append(end if end is not None else int(t) + dur)
    out["expire_tick"] = ends
    return out[SMOKE_COLUMNS].reset_index(drop=True)


@dataclass
class SmokeIndex:
    starts: np.ndarray
    ends: np.ndarray
    centers: list[Vec]
    radius: float

    @classmethod
    def from_table(cls, smokes: pd.DataFrame, tickrate: int, radius: float = SMOKE_RADIUS,
                   z_offset: float = SMOKE_CENTER_Z_OFFSET, bloom_s: float = SMOKE_BLOOM_SECONDS) -> SmokeIndex:
        if smokes is None or smokes.empty:
            return cls(np.array([]), np.array([]), [], radius)
        return cls(
            (smokes["detonate_tick"].to_numpy() + int(round(bloom_s * tickrate))),
            smokes["expire_tick"].to_numpy(),
            [(float(x), float(y), float(z) + z_offset) for x, y, z in zip(smokes["x"], smokes["y"], smokes["z"])],
            radius,
        )

    def active(self, tick: int) -> list[Vec]:
        if not len(self.starts):
            return []
        idx = np.nonzero((self.starts <= tick) & (tick < self.ends))[0]
        return [self.centers[i] for i in idx]

    def blocks(self, tick: int, a: Vec, b: Vec, active: list[Vec] | None = None) -> bool:
        for c in self.active(tick) if active is None else active:
            if segment_sphere(a, b, c, self.radius):
                return True
        return False
