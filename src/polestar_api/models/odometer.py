"""Odometer — simple odometer reading from the odometer service."""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import ProtoMessage


@dataclass(frozen=True)
class OdometerStatus(ProtoMessage, schema={1: "odometer_km"}):
    """Odometer reading.

    The odometer service returns a simpler structure than the full dashboard.
    Field mapping is inferred from the dashboard proto (field 17 = odometer_km)
    but the odometer service wraps it at field 1 of its own response.
    """

    odometer_km: float = 0.0
