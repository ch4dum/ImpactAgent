"""Visibility: can player A see player B at tick t? (spec §0)

One interface, two backends:

- ``SpottedBackend``: the game's ``approximate_spotted_by`` (radar spotting).
- ``RaycastBackend``: line of sight against the awpy-data map mesh, from A's eye
  (Z + 64 + m_flDuckViewOffset) to B's head / chest / feet, with
  - lag compensation: B's position at any of the last ``LAG_COMP_WINDOW_TICKS`` ticks counts,
  - smokes as spheres (``SmokeIndex``),
  - a field-of-view cone around A's view direction (``VISIBILITY_FOV_DEG``).

Usage::

    backend = RaycastBackend.for_demo(parsed)          # or SpottedBackend()
    states = TickStates.load(parser, backend.ticks_needed(q["tick"]), spotted=backend.needs_spotted)
    q = check_pairs(backend, states, q)                 # q: tick, observer_id, target_id

The raycast backend needs ``pip install -e .[visibility]`` (awpy).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from impactagent.constants import LAG_COMP_WINDOW_TICKS, VISIBILITY_FOV_DEG
from impactagent.visibility.geometry import angle_deg, eye, target_points, view_dir
from impactagent.visibility.smoke import SmokeIndex
from impactagent.visibility.states import TickStates

__all__ = ["Sight", "VisibilityBackend", "SpottedBackend", "RaycastBackend", "TickStates", "SmokeIndex",
           "check_pairs", "load_mesh", "get_backend"]


@dataclass(frozen=True)
class Sight:
    visible: bool | None  # None = no state for one of the players at that tick
    offset: int | None = None  # raycast: first lag-comp rewind (ticks) at which the target was seen


class VisibilityBackend(ABC):
    name: str = ""
    needs_spotted: bool = False

    def ticks_needed(self, ticks: Iterable[int]) -> set[int]:
        """Ticks whose state `sees` reads (t and t - 1: a target who dies in tick t was alive at t - 1)."""
        return {int(t) - d for t in ticks for d in (0, 1)}

    @abstractmethod
    def sees(self, states: TickStates, tick: int, observer: str, target: str) -> Sight: ...


def _alive_tick(states: TickStates, tick: int, observer: str, target: str) -> int | None:
    """Tick to read the target at, or None if either player has no state / is dead.

    The observer must be alive at `tick`. The target may die during `tick` (e.g. the kill shot):
    then his last alive state (tick - 1) is used.
    """
    o, t = states.get(tick, observer), states.get(tick, target)
    if o is None or t is None or not o[6]:
        return None
    if t[6]:
        return tick
    prev = states.get(tick - 1, target)
    return tick - 1 if prev is not None and prev[6] else None


class SpottedBackend(VisibilityBackend):
    """The game's radar spotting. No FOV / smoke / lag handling (the game decides)."""

    name = "spotted"
    needs_spotted = True

    def sees(self, states, tick, observer, target):
        if states.get(tick, observer) is None or states.get(tick, target) is None:
            return Sight(None)
        tt = _alive_tick(states, tick, observer, target)
        by = states.spotted_by(tt, target) if tt is not None else None
        return Sight(bool(by is not None and observer in by))


class RaycastBackend(VisibilityBackend):
    """Line of sight on the map mesh + lag window + smoke spheres + FOV.

    Set ``smokes=None`` / ``fov_deg=None`` / ``lag_window=0`` to switch a part off.
    """

    name = "raycast"

    def __init__(self, mesh, smokes: SmokeIndex | None = None, fov_deg: float | None = VISIBILITY_FOV_DEG,
                 lag_window: int = LAG_COMP_WINDOW_TICKS):
        self.mesh = mesh
        self.smokes = smokes
        self.fov_deg = fov_deg
        self.lag_window = lag_window
        self.rays = 0

    @classmethod
    def for_demo(cls, parsed, **kw) -> RaycastBackend:
        smokes = SmokeIndex.from_table(getattr(parsed, "smokes", None), parsed.tickrate)
        return cls(load_mesh(parsed.map_name, getattr(parsed, "client_build", None)), smokes=smokes, **kw)

    def ticks_needed(self, ticks):
        return {int(t) - d for t in ticks for d in range(max(self.lag_window, 0) + 2)}

    def sees(self, states, tick, observer, target):
        o = states.get(tick, observer)
        if o is None or states.get(tick, target) is None:
            return Sight(None)
        tt = _alive_tick(states, tick, observer, target)
        if tt is None:
            return Sight(False)
        a = eye(o)
        view = view_dir(o[4], o[5]) if self.fov_deg is not None else None
        active = self.smokes.active(tick) if self.smokes is not None else []
        for d in range(self.lag_window + 1):
            t = states.get(tt - d, target)
            if t is None or not t[6]:
                continue
            for p in target_points(t):
                if view is not None and angle_deg(a, p, view) > self.fov_deg:
                    continue
                if active and self.smokes.blocks(tick, a, p, active):
                    continue
                self.rays += 1
                if self.mesh.is_visible(a, p):
                    return Sight(True, tick - (tt - d))
        return Sight(False)


def check_pairs(backend: VisibilityBackend, states: TickStates, q: pd.DataFrame,
                tick_col: str = "tick", observer_col: str = "observer_id", target_col: str = "target_id") -> pd.DataFrame:
    """Add `visible` (boolean, NA = no state) and `seen_offset` to a copy of `q`."""
    res = [backend.sees(states, int(t), str(o), str(v)) for t, o, v in zip(q[tick_col], q[observer_col], q[target_col])]
    out = q.copy()
    out["visible"] = pd.array([r.visible for r in res], dtype="boolean")
    out["seen_offset"] = pd.array([r.offset for r in res], dtype="Int64")
    return out


def load_mesh(map_name: str, build: int | None = None):
    """awpy-data mesh for the map, from the release matching the demo's build if there is one."""
    try:
        from awpy import VisibilityChecker
        from awpy import data as awpy_data
    except ImportError as exc:  # pragma: no cover
        raise ImportError("The raycast visibility backend needs awpy: pip install -e .[visibility]") from exc
    version = None
    if build is not None:
        try:
            awpy_data.mesh_path(map_name, build)
            version = build
        except FileNotFoundError:
            version = None  # newest cached release
    return VisibilityChecker(map_name, version=version)


def get_backend(name: str, parsed=None, **kw) -> VisibilityBackend:
    if name == "spotted":
        return SpottedBackend()
    if name == "raycast":
        if parsed is None:
            raise ValueError("raycast backend needs the parsed demo (map, build, smokes)")
        return RaycastBackend.for_demo(parsed, **kw)
    raise ValueError(f"unknown visibility backend {name!r} (spotted | raycast)")
