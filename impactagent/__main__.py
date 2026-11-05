"""CLI: python -m impactagent {inspect,parse,validate,validate-all,visibility} <demo>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_inspect(args: argparse.Namespace) -> int:
    from impactagent.parse.demo import _demo_file

    with _demo_file(args.demo) as (dem_path, _sha):
        return _inspect(dem_path, args.events)


def _demo_stem(path: Path) -> str:
    name = path.name
    for ext in (".bz2", ".gz", ".zst"):
        name = name.removesuffix(ext)
    return name.removesuffix(".dem")


def _inspect(dem_path: Path, event_names: list[str]) -> int:
    import pandas as pd
    from demoparser2 import DemoParser

    parser = DemoParser(str(dem_path))
    print("header:", parser.parse_header())
    events = sorted(parser.list_game_events())
    print(f"\ngame events ({len(events)}):")
    for e in events:
        print("  ", e)
    for name in event_names:
        try:
            df = pd.DataFrame(parser.parse_event(name))
        except Exception as exc:  # noqa: BLE001
            print(f"\n[{name}] error: {exc}")
            continue
        print(f"\n[{name}] rows={len(df)}")
        for c in df.columns:
            print(f"   {c:<28} {str(df[c].dtype):<10} e.g. {df[c].iloc[0] if len(df) else ''!r}")
    try:
        inv = pd.DataFrame(parser.parse_ticks(["inventory"], ticks=[10000]))
        print("\n[parse_ticks inventory] columns:", list(inv.columns))
        if len(inv):
            print("   e.g.", inv.iloc[0].to_dict())
    except Exception as exc:  # noqa: BLE001
        print("\n[parse_ticks inventory] error:", exc)
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    from impactagent.parse.demo import parse_demo

    p = parse_demo(args.demo)
    out = Path(args.out or f"data/parsed/{_demo_stem(Path(args.demo))}")
    out.mkdir(parents=True, exist_ok=True)
    tables = p.tables()
    det = p.grenades.attrs.get("detonations")
    if det is not None and not det.empty:
        tables["detonations"] = det
    for name, df in tables.items():
        df = df.copy()
        df.attrs = {}
        for c in df.columns:  # lists (inventory) -> parquet list; mixed objects -> string
            if df[c].dtype == object and not df[c].map(lambda v: isinstance(v, (list, type(None)))).all():
                df[c] = df[c].astype("string")
        df.to_parquet(out / f"{name}.parquet", index=False)
        print(f"{name:<20} {len(df):>6} rows")
    print(f"map={p.map_name} rounds={len(p.rounds)} sha256={p.sha256[:12]} -> {out}")
    for w in p.warnings:
        print("WARN:", w)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from impactagent.validate import validate

    return validate(args.demo, args.truth, metrics=args.metrics, only_diff=args.only_diff, force=args.force)


def _cmd_validate_all(args: argparse.Namespace) -> int:
    from impactagent.validate import validate_all

    return validate_all(args.dir, metrics=args.metrics)


def _cmd_visibility(args: argparse.Namespace) -> int:
    from impactagent.visibility.report import run

    return run(args.demos)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles + non-ASCII player names
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="impactagent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("inspect", help="list game events and event columns")
    i.add_argument("demo", type=Path)
    i.add_argument(
        "--events",
        nargs="*",
        default=["player_death", "player_hurt", "weapon_fire", "player_blind", "round_end"],
    )
    i.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("parse", help="parse demo and write tables to Parquet")
    p.add_argument("demo", type=Path)
    p.add_argument("--out")
    p.set_defaults(func=_cmd_parse)

    v = sub.add_parser("validate", help="compare our metrics with ground truth JSON")
    v.add_argument("demo", type=Path)
    v.add_argument("--truth", type=Path, required=True)
    v.add_argument("--metrics", nargs="*", help="only these metrics")
    v.add_argument("--only-diff", action="store_true", help="hide rows that match")
    v.add_argument("--force", action="store_true", help="compare even if demo/truth look like different matches")
    v.set_defaults(func=_cmd_validate)

    va = sub.add_parser("validate-all", help="validate every truth JSON in a folder against its demo")
    va.add_argument("--dir", default="data/validation")
    va.add_argument("--metrics", nargs="*", help="only these metrics")
    va.set_defaults(func=_cmd_validate_all)

    vis = sub.add_parser("visibility", help="kill visibility report per backend (needs .[visibility])")
    vis.add_argument("demos", nargs="+", type=Path)
    vis.set_defaults(func=_cmd_visibility)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
