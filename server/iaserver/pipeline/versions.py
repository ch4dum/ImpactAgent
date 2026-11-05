"""Versions of every layer of a bundle (docs/design/backend.md §3).

pipeline_version = p{N}-m{sha8 registry.yaml}-wp{N}-c{sha8 credit.yaml}-is{N}
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from impactagent.metrics.registry import REGISTRY_PATH
from impactagent.ratings.credit import CFG_PATH
from impactagent.ratings.wp_model import _MODEL_PATH

# Bump by hand when the parser's tables / rules or the state snapshot change (events/, snapshot/).
PARSE_VERSION = "p1"
# Bump by hand when impact-spec credit rules change in code without a credit.yaml change.
IMPACT_SPEC_REV = "is1"
# Bundle layout (manifest format).
BUNDLE_FORMAT = 1


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _wp_tag(model_path: Path) -> str:
    m = re.search(r"v(\d+)$", model_path.stem)
    return f"wp{m.group(1)}" if m else model_path.stem


def _git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent,
                             capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return None
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def components() -> dict:
    """Every input that decides a bundle's content, with full hashes."""
    return {
        "parse_version": PARSE_VERSION,
        "metrics_sha256": _sha(REGISTRY_PATH),
        "wp_model": _MODEL_PATH.stem,
        "wp_model_sha256": _sha(_MODEL_PATH),
        "credit_sha256": _sha(CFG_PATH),
        "impact_spec": IMPACT_SPEC_REV,
        "git_sha": _git_sha(),
        "bundle_format": BUNDLE_FORMAT,
    }


def pipeline_version(c: dict | None = None) -> str:
    c = c or components()
    return (f"{c['parse_version']}-m{c['metrics_sha256'][:8]}-{_wp_tag(Path(c['wp_model']))}"
            f"-c{c['credit_sha256'][:8]}-{c['impact_spec']}")
