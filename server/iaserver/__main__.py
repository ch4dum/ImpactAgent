"""CLI: python -m iaserver bundle DEMO [--out DIR]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from impactagent.constants import PARSE_TIMEOUT_SECONDS


def _demo_stem(path: Path) -> str:
    name = path.name
    for ext in (".bz2", ".gz", ".zst"):
        name = name.removesuffix(ext)
    return name.removesuffix(".dem")


def _cmd_bundle(args: argparse.Namespace) -> int:
    from iaserver.pipeline.bundle import write_bundle
    from iaserver.pipeline.run import run_match

    b = run_match(args.demo, timeout=args.timeout or None)
    out = Path(args.out or f"data/bundles/{_demo_stem(args.demo)}")
    m = write_bundle(b, out)
    for layer, info in m["layers"].items():
        size = sum(f["bytes"] for f in info["files"].values())
        print(f"{layer:<9} {info['prefix']:<40} {len(info['files']):>3} files {size / 1024:>8.1f} KB")
    print(f"map={b.map_name} rounds={b.rounds_played} dem_sha256={b.sha256[:12]} "
          f"pipeline_version={b.pipeline_version} -> {out}")
    print("timings_s:", m["timings_s"])
    for w in b.warnings:
        print("WARN:", w)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="iaserver")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bundle", help="demo -> bundle folder (events / snapshot / derived + manifest)")
    b.add_argument("demo", type=Path)
    b.add_argument("--out", help="default data/bundles/<demo stem>")
    b.add_argument("--timeout", type=float, default=PARSE_TIMEOUT_SECONDS,
                   help=f"parse timeout in s (default {PARSE_TIMEOUT_SECONDS}; 0 = none, parse in-process)")
    b.set_defaults(func=_cmd_bundle)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
