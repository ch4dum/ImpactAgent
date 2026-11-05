"""Train the round-win probability model (WP, impact-spec §2.2 / §2.4).

`python -m impactagent train-wp data/parsed/wp_states.parquet` compares feature sets with
GroupKFold CV (groups = match), picks C per set, fits the chosen set on all data and writes
`impactagent/ratings/wp_model_v2.json` (standardization mean/std + coefficients; v1 is kept
unchanged, v2 uses the kit-aware ct_can_defuse). Prediction
lives in `wp_model.py` and needs numpy only; scikit-learn is imported in this file alone
(`pip install -e .[train]`).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from impactagent.ratings.wp_model import (
    _MODEL_PATH,
    RULE_FIXED,
    feature_matrix,
    predict_wp,
    reliability_table,
)

BASE = ["t_alive", "ct_alive", "bomb_planted", "time_left_pre", "time_left_post", "equip_diff_k"]
FEATURE_SETS: dict[str, list[str]] = {
    "A": BASE,
    "B": BASE + ["map_dust2", "map_mirage"],
    "C": BASE + ["map_dust2", "map_mirage", "alive_prod"],
    "D": BASE + ["map_dust2", "map_mirage", "alive_prod", "ct_can_defuse"],
    "E": BASE + ["map_dust2", "map_mirage", "alive_prod", "ct_can_defuse", "ct_has_kit"],
}
C_GRID = (0.01, 0.1, 1.0, 10.0)
# Default set (impact-spec §2.2): D. Its CV log loss is within fold noise of A (Δ ≈ 0.002,
# fold std ≈ 0.009) but only D gets the post-plant clock right — without ct_can_defuse,
# time_left_post has a positive coefficient (less C4 time -> lower T WP, wrong direction).
DEFAULT_SET = "D"
N_FOLDS = 5
# Empirical baseline: Laplace-style smoothing toward the global T win rate.
BASELINE_ALPHA = 2.0
EPS = 1e-6


def round_weights(df: pd.DataFrame) -> np.ndarray:
    """1 / number of trainable rows of the row's round (every round weighs 1)."""
    n = df.groupby(["match_id", "round_no"])["tick"].transform("size").to_numpy()
    return 1.0 / n


def _brier(y, p, w) -> float:
    return float(np.average((p - y) ** 2, weights=w))


def _logloss(y, p, w) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(np.average(-(y * np.log(p) + (1 - y) * np.log(1 - p)), weights=w))


def _fit_logreg(X, y, w, C):
    from sklearn.linear_model import LogisticRegression

    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    Z = (X - mean) / std
    m = LogisticRegression(C=C, solver="lbfgs", max_iter=2000)  # L2 (default)
    m.fit(Z, y, sample_weight=w * len(w) / w.sum())  # rescale so C means the same per set
    return {"mean": mean, "std": std, "coef": m.coef_[0], "intercept": float(m.intercept_[0])}


def _predict_logreg(fit, X):
    z = ((X - fit["mean"]) / fit["std"]) @ fit["coef"] + fit["intercept"]
    return 1.0 / (1.0 + np.exp(-z))


def _baseline_fit(df: pd.DataFrame, w: np.ndarray):
    keys = ["t_alive", "ct_alive", "bomb_planted"]
    g = pd.DataFrame({k: df[k].to_numpy() for k in keys})
    g["w"] = w
    g["wy"] = w * df["t_won"].to_numpy()
    prior = g["wy"].sum() / g["w"].sum()
    tab = g.groupby(keys)[["w", "wy"]].sum()
    tab["p"] = (tab["wy"] + BASELINE_ALPHA * prior) / (tab["w"] + BASELINE_ALPHA)
    return tab["p"].to_dict(), prior


def _baseline_predict(fit, df: pd.DataFrame) -> np.ndarray:
    tab, prior = fit
    keys = zip(df["t_alive"], df["ct_alive"], df["bomb_planted"])
    return np.array([tab.get(k, prior) for k in keys], dtype=float)


def _cv(df: pd.DataFrame, w: np.ndarray, y: np.ndarray, groups: np.ndarray):
    """-> {name: {"C": best C, "brier": (mean, std), "logloss": (mean, std), "oof": array}}"""
    from sklearn.model_selection import GroupKFold

    folds = list(GroupKFold(n_splits=N_FOLDS).split(df, y, groups))
    out = {}

    def score(pred_fn):
        b, l, oof = [], [], np.zeros(len(y))
        for tr, te in folds:
            p = pred_fn(tr, te)
            oof[te] = p
            b.append(_brier(y[te], p, w[te]))
            l.append(_logloss(y[te], p, w[te]))
        return (np.mean(b), np.std(b)), (np.mean(l), np.std(l)), oof

    bb, bl, oof = score(lambda tr, te: _baseline_predict(_baseline_fit(df.iloc[tr], w[tr]), df.iloc[te]))
    out["baseline"] = {"C": None, "brier": bb, "logloss": bl, "oof": oof, "per_C": {}}

    for name, feats in FEATURE_SETS.items():
        X = feature_matrix(df, feats)
        best = None
        per_c = {}
        for C in C_GRID:
            b, l, oof = score(lambda tr, te: _predict_logreg(_fit_logreg(X[tr], y[tr], w[tr], C), X[te]))
            per_c[C] = (b, l)
            if best is None or l[0] < best["logloss"][0]:
                best = {"C": C, "brier": b, "logloss": l, "oof": oof}
        best["per_C"] = per_c
        out[name] = best
    return out


def _manifest_hash(df: pd.DataFrame) -> str:
    keys = sorted(df["match_id"].unique())
    return hashlib.sha256("\n".join(keys).encode()).hexdigest()


def _sanity(model: dict) -> list[tuple[str, float]]:
    """Hand-made states -> WP_T (impact-spec §2.4)."""
    def st(t, ct, bomb=0, tl=115.0, eq=0.0, m="de_dust2"):
        return {"t_alive": t, "ct_alive": ct, "bomb_planted": bomb, "time_left_s": tl,
                "equip_diff_k": eq, "map": m, "event_type": "freeze_end", "trainable": True,
                "t_won": 0}

    # Full buy: T 5×~4.7k = 23.5k, CT 5×~5.2k = 26k -> equip_diff ≈ -2.5k.
    cases = [
        ("5v5 freeze end, full buy both (eq -2.5k)", st(5, 5, eq=-2.5)),
        ("5v5 freeze end, eq 0", st(5, 5)),
        ("5v4 (T up a player), 90s left", st(5, 4, tl=90, eq=2.0)),
        ("5v5, 90s left", st(5, 5, tl=90)),
        ("4v4 pre-plant, 40s left", st(4, 4, tl=40)),
        ("4v4 just planted (40s on C4)", st(4, 4, bomb=1, tl=40)),
        ("2v2 planted, 30s left", st(2, 2, bomb=1, tl=30)),
        ("2v2 planted, 12s left", st(2, 2, bomb=1, tl=12)),
        ("2v2 planted, 8s left (CT can't defuse w/o kit)", st(2, 2, bomb=1, tl=8)),
        ("2v2 planted, 3s left", st(2, 2, bomb=1, tl=3)),
        ("5v5 eco T (eq -15k)", st(5, 5, eq=-15.0)),
        ("5v5 eco CT (eq +15k)", st(5, 5, eq=15.0)),
    ]
    df = pd.DataFrame([c for _, c in cases])
    p = predict_wp(df, model=model)
    return [(name, float(v)) for (name, _), v in zip(cases, p)]


def build_faceit_states(demo: str | Path, out: str | Path, member: str = "haineieie") -> pd.DataFrame:
    """wp_states of one held-out demo (never trained on) + `team_t`: the FACEIT team name
    ("team_<member>") on the T side of each round, else "other"."""
    from impactagent.parse.demo import parse_demo
    from impactagent.ratings.wp_states import build_wp_states

    p = parse_demo(demo, fast=True)
    df, _stats = build_wp_states(p)
    names = p.players.set_index("steam_id")["name"].astype(str)
    sid = names[names.str.casefold() == member.casefold()].index
    if not len(sid):
        raise ValueError(f"player {member!r} not in {demo}")
    prs = p.player_rounds_side
    side = prs[prs["steam_id"] == sid[0]].set_index("round_no")["side"]
    df["team_t"] = np.where(df["round_no"].map(side) == "T", f"team_{member}", "other")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


def _faceit_report(model: dict, faceit_states: Path, team: str) -> None:
    fs = pd.read_parquet(faceit_states)
    fe = fs[fs["event_type"] == "freeze_end"].copy()
    fe["wp_t"] = predict_wp(fe, model=model).to_numpy()
    if "team_t" not in fe:
        print(f"  {faceit_states}: no team_t column, skipped")
        return
    t_rows = fe[fe["team_t"] == team]
    ct_rows = fe[fe["team_t"] != team]
    print(f"  FACEIT {faceit_states.name}: team {team}")
    if len(t_rows):
        print(f"    as T : {len(t_rows):>2} rounds, mean WP at freeze end = {t_rows['wp_t'].mean():.1%} "
              f"(won {int(t_rows['t_won'].sum())})  FACEIT ≈ 61%")
    if len(ct_rows):
        wp_ct = 1 - ct_rows["wp_t"]
        print(f"    as CT: {len(ct_rows):>2} rounds, mean WP at freeze end = {wp_ct.mean():.1%} "
              f"(won {int((1 - ct_rows['t_won']).sum())})  FACEIT ≈ 55%")


def run_train_wp(
    states_path: str | Path,
    out: str | Path = _MODEL_PATH,
    chosen: str | None = None,
    faceit_states: str | Path | None = None,
    faceit_team: str = "team_haineieie",
) -> int:
    all_states = pd.read_parquet(states_path)
    df = all_states[all_states["trainable"]].reset_index(drop=True)
    y = df["t_won"].to_numpy().astype(int)
    w = round_weights(df)
    groups = df["match_id"].to_numpy()

    print(f"train-wp: {states_path}")
    print(f"  matches {df['match_id'].nunique()}, rounds {df.groupby(['match_id', 'round_no']).ngroups}, "
          f"trainable rows {len(df)}; GroupKFold {N_FOLDS} by match; weight = 1/rows per round")
    res = _cv(df, w, y, groups)

    print("\n  CV (round-weighted, mean ± std over folds)")
    print(f"  {'set':<9}{'best C':>8}{'Brier':>18}{'log loss':>18}")
    for name, r in res.items():
        c = "-" if r["C"] is None else f"{r['C']:g}"
        print(f"  {name:<9}{c:>8}   {r['brier'][0]:.4f} ± {r['brier'][1]:.4f}   "
              f"{r['logloss'][0]:.4f} ± {r['logloss'][1]:.4f}")
    print("\n  log loss per C:")
    for name in FEATURE_SETS:
        row = "  ".join(f"C={c:g}: {v[1][0]:.4f}" for c, v in res[name]["per_C"].items())
        print(f"    {name}: {row}")

    cv_best = min(FEATURE_SETS, key=lambda k: res[k]["logloss"][0])
    print(f"\n  lowest CV log loss: set {cv_best}")
    if chosen is None:
        chosen = DEFAULT_SET
    feats = FEATURE_SETS[chosen]
    C = res[chosen]["C"]
    print(f"\n  chosen: set {chosen} (C={C:g}) features={feats}")

    rel = reliability_table(res[chosen]["oof"], y, w)
    print("\n  reliability (out-of-fold, set " + chosen + ", round-weighted)")
    print(f"  {'bin':<12}{'rows':>6}{'pred':>8}{'actual':>8}")
    for r in rel:
        print(f"  {r['bin']:<12}{r['rows']:>6}{r['pred']:>8.3f}{r['actual']:>8.3f}")

    X = feature_matrix(df, feats)
    fit = _fit_logreg(X, y, w, C)
    model = {
        "name": Path(out).stem,
        "kind": "logistic_regression_l2_standardized",
        "C": C,
        "features": feats,
        "mean": fit["mean"].tolist(),
        "std": fit["std"].tolist(),
        "intercept": fit["intercept"],
        "coefficients": fit["coef"].tolist(),
        "training": {
            "matches": int(df["match_id"].nunique()),
            "rounds": int(df.groupby(["match_id", "round_no"]).ngroups),
            "rows": int(len(df)),
            "sample_weight": "1/trainable rows per round",
            "manifest_sha256": _manifest_hash(df),
            "cv": {k: {"C": v["C"], "brier": list(v["brier"]), "logloss": list(v["logloss"])}
                   for k, v in res.items()},
        },
        "rule_fixed": RULE_FIXED,
    }
    Path(out).write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

    print("\n  coefficients (standardized; raw = per unit of the feature)")
    print(f"  {'feature':<16}{'std coef':>10}{'raw coef':>10}{'mean':>9}{'std':>8}")
    for f, c, m, s in zip(feats, fit["coef"], fit["mean"], fit["std"]):
        print(f"  {f:<16}{c:>10.3f}{c / s:>10.4f}{m:>9.2f}{s:>8.2f}")
    print(f"  intercept {fit['intercept']:.3f}")

    print("\n  sanity (WP of T)")
    for name, v in _sanity(model):
        print(f"    {name:<48} {v:.1%}")

    if faceit_states:
        print()
        _faceit_report(model, Path(faceit_states), faceit_team)

    print(f"\n  model -> {out}")
    return 0
