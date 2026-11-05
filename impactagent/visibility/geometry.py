"""Eye / target points and angles (Hammer units, Z up, pitch > 0 = looking down)."""

from __future__ import annotations

import math

from impactagent.constants import EYE_HEIGHT_STANDING, TARGET_CHEST_FRACTION, TARGET_FEET_OFFSET

Vec = tuple[float, float, float]


def eye_height(duck_view_offset: float) -> float:
    return EYE_HEIGHT_STANDING + duck_view_offset


def eye(state) -> Vec:
    x, y, z, dvo = state[:4]
    return (x, y, z + eye_height(dvo))


def target_points(state) -> tuple[Vec, Vec, Vec]:
    """Head, chest, feet of a player."""
    x, y, z, dvo = state[:4]
    h = eye_height(dvo)
    return (x, y, z + h), (x, y, z + TARGET_CHEST_FRACTION * h), (x, y, z + TARGET_FEET_OFFSET)


def view_dir(pitch: float, yaw: float) -> Vec:
    p, y = math.radians(pitch), math.radians(yaw)
    return (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p))


def angle_deg(a: Vec, b: Vec, view: Vec) -> float:
    """Angle between `view` and the direction a -> b."""
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
    if n == 0:
        return 0.0
    c = (d[0] * view[0] + d[1] * view[1] + d[2] * view[2]) / n
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def segment_sphere(a: Vec, b: Vec, c: Vec, r: float) -> bool:
    """Does segment a-b pass within r of c (end points inside count)?"""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    L2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (ac[0] * ab[0] + ac[1] * ab[1] + ac[2] * ab[2]) / L2))
    p = (a[0] + ab[0] * t - c[0], a[1] + ab[1] * t - c[1], a[2] + ab[2] * t - c[2])
    return p[0] ** 2 + p[1] ** 2 + p[2] ** 2 <= r * r
