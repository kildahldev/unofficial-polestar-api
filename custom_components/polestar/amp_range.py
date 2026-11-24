"""Charge current range for the amp-limit number (no HA imports)."""

from __future__ import annotations

from typing import Any

DEFAULT_AMP_RANGE = (6, 32)


def amp_limit_range(limits: Any) -> tuple[int, int]:
    """Use the car-reported (min, max) when both are known, else the default.

    The app limits its +/- control to the same car-information values.
    """
    lo = getattr(limits, "min_amps", None)
    hi = getattr(limits, "max_amps", None)
    if lo is None or hi is None:
        return DEFAULT_AMP_RANGE
    return (lo, hi)
