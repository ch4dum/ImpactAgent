"""Round-win probability model (WP) — prediction only, no scikit-learn.

The model is an L2 logistic regression on standardized features, fitted by `train_wp.py`
(scikit-learn, training only). Its parameters are plain JSON (`wp_model_v2.json`: features,
mean, std, coefficients, intercept) and prediction here is pure numpy. `predict_wp` returns
WP from the T side's point of view for each state row; rows marked `trainable=False` get a
WP fixed by rule (impact-spec §2.2) instead of the model.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# v2 = v1 features with a kit-aware ct_can_defuse (wp_states.ct_has_kit). v1 is kept as is.
_MODEL_PATH = Path(__file__).with_name("wp_model_v2.json")

# Maps with >= 5 training matches get their own intercept; every other map is all-zero
# (falls back to the global intercept). impact-spec §2.2.
KEPT_MAPS = ("de_dust2", "de_mirage")

# Seconds of C4 left a CT needs to start a defuse: 5 s with a kit, 10 s without. A state
# without kit info (no `ct_has_kit` column, e.g. wp_states built before v2) uses the no-kit time.
DEFUSE_S_KIT = 5.0
DEFUSE_S_NO_KIT = 10.0

RULE_FIXED = {
    "round_end": "t_won",
    "defuse": 0.0,
    "explode": 1.0,
    "ct_alive_0": 1.0,
    "t_alive_0_no_bomb": 0.0,
}


def load_model(path: str | Path = _MODEL_PATH) -> dict:
    """Return the model dict {features, mean, std, intercept, coefficients, ...}."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def feature_matrix(states: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Raw (unstandardized) feature matrix, deriving the engineered columns exactly as at
    training time: time_left_pre/post, alive_prod, map one-hot, ct_can_defuse."""
    planted = states["bomb_planted"].to_numpy().astype(float)
    time_left = states["time_left_s"].to_numpy().astype(float)
    t_alive = states["t_alive"].to_numpy().astype(float)
    ct_alive = states["ct_alive"].to_numpy().astype(float)
    mp = states["map"].to_numpy()

    if "ct_has_kit" in states:
        kit = states["ct_has_kit"].fillna(False).to_numpy(dtype=bool)
    else:
        kit = np.zeros(len(states), dtype=bool)
    need = np.where(kit, DEFUSE_S_KIT, DEFUSE_S_NO_KIT)
    if "ct_defusing" in states:  # a defuse in progress that will finish in time
        defusing = states["ct_defusing"].fillna(False).to_numpy(dtype=bool)
    else:
        defusing = np.zeros(len(states), dtype=bool)

    cols = {
        "t_alive": t_alive,
        "ct_alive": ct_alive,
        "bomb_planted": planted,
        "time_left_pre": np.where(planted == 1, 0.0, time_left),
        "time_left_post": np.where(planted == 1, time_left, 0.0),
        "equip_diff_k": states["equip_diff_k"].to_numpy().astype(float),
        "alive_prod": t_alive * ct_alive,
        # 1 after the plant while a surviving CT still has time to defuse (5 s with a kit,
        # 10 s without) or a defuse that will finish in time is already running; 0 otherwise
        # (pre-plant it is 0, so it acts as an interaction with bomb_planted).
        "ct_can_defuse": ((planted == 1) & ((time_left >= need) | defusing)).astype(float),
        # 1 after the plant while a surviving CT has a kit (CV candidate, set E).
        "ct_has_kit": ((planted == 1) & kit).astype(float),
    }
    for m in KEPT_MAPS:
        cols["map_" + m.removeprefix("de_")] = (mp == m).astype(float)

    return np.column_stack([cols[f] for f in features])


def rule_fixed_wp(states: pd.DataFrame) -> pd.Series:
    """WP by rule for rows the model must not predict (impact-spec §2.2)."""
    et = states["event_type"].to_numpy()
    t_alive = states["t_alive"].to_numpy()
    ct_alive = states["ct_alive"].to_numpy()
    bomb = states["bomb_planted"].to_numpy()
    t_won = states["t_won"].to_numpy()

    wp = np.full(len(states), np.nan)
    wp[et == "round_end"] = t_won[et == "round_end"]
    wp[et == "defuse"] = 0.0
    wp[et == "explode"] = 1.0
    wp[ct_alive == 0] = 1.0
    wp[(t_alive == 0) & (bomb == 0)] = 0.0
    return pd.Series(wp, index=states.index, dtype="float64")


def predict_wp(states: pd.DataFrame, model: dict | None = None) -> pd.Series:
    """WP (T side) for every row of a wp_states frame.

    trainable rows -> model (standardized logistic); rule-fixed rows -> rule value (§2.2).
    """
    model = model or load_model()
    features = model["features"]
    mean = np.asarray(model["mean"], dtype=float)
    std = np.asarray(model["std"], dtype=float)
    coef = np.asarray(model["coefficients"], dtype=float)

    Z = (feature_matrix(states, features) - mean) / std
    logit = Z @ coef + float(model["intercept"])
    prob = 1.0 / (1.0 + np.exp(-np.clip(logit, -500.0, 500.0)))

    out = pd.Series(prob, index=states.index, dtype="float64")
    if "trainable" in states:
        trainable = states["trainable"].to_numpy(dtype=bool)
    else:
        trainable = np.ones(len(states), dtype=bool)
    return out.where(trainable, rule_fixed_wp(states))


def reliability_table(pred: np.ndarray, y: np.ndarray, w: np.ndarray | None = None, bins: int = 10):
    """10 equal-width WP bins -> [{bin, rows, pred (weighted mean), actual (weighted)}]."""
    w = np.ones(len(pred)) if w is None else w
    idx = np.minimum((pred * bins).astype(int), bins - 1)
    rows = []
    for b in range(bins):
        m = idx == b
        if not m.any():
            rows.append({"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "rows": 0,
                         "pred": float("nan"), "actual": float("nan")})
            continue
        rows.append({
            "bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}",
            "rows": int(m.sum()),
            "pred": float(np.average(pred[m], weights=w[m])),
            "actual": float(np.average(y[m], weights=w[m])),
        })
    return rows
