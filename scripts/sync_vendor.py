#!/usr/bin/env python3
"""Keep custom_components/polestar/vendor/polestar_api in sync with src/polestar_api.

The HA integration vendors this library (see custom_components/polestar/__init__.py)
instead of depending on the unofficial-polestar-api PyPI package, so HACS users get
this fork's fixes without needing a new PyPI release. src/polestar_api remains the
single source of truth for development, tests, and docs; this script copies it into
the vendor directory, or checks that the vendor directory is up to date.

Usage:
    python scripts/sync_vendor.py          # copy src/polestar_api -> vendor
    python scripts/sync_vendor.py --check  # exit 1 if vendor is out of date (for CI)
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "polestar_api"
VENDOR = ROOT / "custom_components" / "polestar" / "vendor" / "polestar_api"

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def _tree_matches() -> bool:
    if not VENDOR.is_dir():
        return False
    comparison = filecmp.dircmp(SRC, VENDOR, ignore=["__pycache__"])
    return _dircmp_matches(comparison)


def _dircmp_matches(comparison: filecmp.dircmp) -> bool:
    if comparison.left_only or comparison.right_only or comparison.diff_files or comparison.funny_files:
        return False
    return all(_dircmp_matches(sub) for sub in comparison.subdirs.values())


def main() -> int:
    check_only = "--check" in sys.argv

    if check_only:
        if _tree_matches():
            print("vendor/polestar_api is up to date with src/polestar_api")
            return 0
        print(
            "custom_components/polestar/vendor/polestar_api is out of date.\n"
            "Run: python scripts/sync_vendor.py",
            file=sys.stderr,
        )
        return 1

    if VENDOR.exists():
        shutil.rmtree(VENDOR)
    shutil.copytree(SRC, VENDOR, ignore=IGNORE)
    print(f"Synced {SRC} -> {VENDOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
