"""Diagnostics support for the Polestar integration."""

from __future__ import annotations

import time
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from polestar_api import grpc as grpc_call

from .const import CONF_VIN, DOMAIN
from .coordinator import PolestarCoordinator

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_VIN,
    "username",
    "internal_id",
    "registration_no",
    "id",
    "location_id",
    "location_alias",
    "latitude",
    "longitude",
    "altitude",
}


def _serialize(value: Any) -> Any:
    """Convert models to JSON-friendly structures, keeping enum names readable."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _serialize(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    return value


def _stream_diagnostics(coordinator: PolestarCoordinator) -> dict[str, Any]:
    """Report liveness of the long-lived streaming subscriptions."""
    now = time.monotonic()
    streams: dict[str, Any] = {}
    for attr in sorted(coordinator._STREAMS):
        task = coordinator._stream_tasks.get(attr)
        last_data = coordinator._stream_last_data.get(attr)
        info: dict[str, Any] = {
            "started": task is not None,
            "running": task is not None and not task.done(),
            "supported": attr not in coordinator._unsupported_streams,
            "seconds_since_last_data": (
                round(now - last_data, 1) if last_data is not None else None
            ),
        }
        if task is not None and task.done() and not task.cancelled():
            err = task.exception()
            if err is not None:
                info["failed_with"] = type(err).__name__
        streams[attr] = info
    return streams


def _api_call_diagnostics() -> dict[str, Any]:
    """Report gRPC call attempts per method since the library was loaded."""
    total = sum(grpc_call.CALL_COUNTS.values())
    elapsed = max(time.time() - grpc_call.CALL_COUNTS_SINCE, 1.0)
    return {
        "total": total,
        "per_method": dict(sorted(grpc_call.CALL_COUNTS.items())),
        "since": datetime.fromtimestamp(grpc_call.CALL_COUNTS_SINCE, UTC).isoformat(),
        "per_day_rate": round(total * 86400 / elapsed, 1),
    }


def _coordinator_diagnostics(coordinator: PolestarCoordinator) -> dict[str, Any]:
    """Dump one vehicle's coordinator state."""
    return {
        "model_name": coordinator.vehicle.model_name,
        "model_year": coordinator.vehicle.model_year,
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval is not None
            else None
        ),
        "last_update_success": coordinator.last_update_success,
        "poll_count": coordinator._poll_count,
        "unsupported_fetches": sorted(coordinator._unsupported_fetches),
        "unsupported_streams": sorted(coordinator._unsupported_streams),
        "unsupported_commands": sorted(coordinator._unsupported_commands),
        "streams": _stream_diagnostics(coordinator),
        "data": async_redact_data(_serialize(coordinator.data), TO_REDACT),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "demo_mode": data["api"] is None,
        "api_calls": _api_call_diagnostics(),
        "vehicles": [
            _coordinator_diagnostics(coordinator)
            for coordinator in data["coordinators"].values()
        ],
    }
