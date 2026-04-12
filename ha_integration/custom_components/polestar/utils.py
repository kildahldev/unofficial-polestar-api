"""Utility helpers for the Polestar integration."""

from __future__ import annotations

from datetime import datetime, time as dt_time
from enum import IntEnum
from typing import Any

from homeassistant.util import dt as dt_util

from polestar_api.models.charge_location import ChargeLocation
from polestar_api.models.common import Timestamp, Weekday
from polestar_api.models.parking_climate_timer import ParkingClimateTimer


_EXCLUDED_ENUM_NAMES = {"UNSPECIFIED", "UNDEFINED", "UNKNOWN"}


def enum_name(value: IntEnum | None, *, allow_unspecified: bool = False) -> str | None:
    """Convert an enum value to a Home Assistant friendly option."""
    if value is None:
        return None
    name = getattr(value, "name", None)
    if not name:
        return None
    if not allow_unspecified and name in _EXCLUDED_ENUM_NAMES:
        return None
    return name.lower()


def enum_options(enum_cls: type[IntEnum], *, exclude_unspecified: bool = True) -> list[str]:
    """Return HA-friendly options for an enum class."""
    options: list[str] = []
    for member in enum_cls:
        if exclude_unspecified and member.name in {"UNSPECIFIED", "UNDEFINED", "UNKNOWN"}:
            continue
        options.append(member.name.lower())
    return options


def time_to_minutes(value: dt_time) -> int:
    """Convert a time object to minutes after midnight."""
    return (value.hour * 60) + value.minute


def minutes_to_time(minutes: int) -> dt_time:
    """Convert minutes after midnight to a time object."""
    total = minutes % (24 * 60)
    return dt_time(hour=total // 60, minute=total % 60)


def local_utc_offset_minutes() -> int:
    """Return the current Home Assistant timezone offset in minutes."""
    now = dt_util.now()
    offset = now.utcoffset()
    if offset is None:
        return 0
    return int(offset.total_seconds() // 60)


def timestamp_to_iso(value: Timestamp | None) -> str | None:
    """Convert a protobuf timestamp to an ISO timestamp string."""
    if value is None:
        return None
    dt_value = datetime.fromtimestamp(value.seconds + (value.nanos / 1_000_000_000), tz=dt_util.UTC)
    return dt_value.isoformat()


def serialize_weekdays(days: tuple[Weekday, ...]) -> list[str]:
    """Serialize weekdays as lowercase names."""
    return [day.name.lower() for day in days]


def serialize_parking_climate_timer(timer: ParkingClimateTimer) -> dict[str, Any]:
    """Serialize a parking climate timer for entity attributes."""
    return {
        "timer_id": timer.timer_id,
        "index": timer.index,
        "ready_at": f"{timer.ready_at_hour:02d}:{timer.ready_at_minute:02d}",
        "activated": timer.activated,
        "repeat": timer.repeat,
        "weekdays": serialize_weekdays(timer.weekdays),
    }


def serialize_charge_location(location: ChargeLocation) -> dict[str, Any]:
    """Serialize a charge location for entity attributes."""
    return {
        "location_id": location.location_id,
        "alias": location.location_alias,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "amp_limit": location.amp_limit,
        "minimum_soc": location.minimum_soc,
        "optimised_charging_enabled": location.is_optimised_charging_enabled,
        "bidirectional_charging_enabled": location.is_bidirectional_charging_enabled,
        "optimised_charging_type": enum_name(location.available_optimised_charging),
        "location_type": enum_name(location.location_type),
        "charge_timers": [
            {
                "id": timer.id,
                "activated": timer.activated,
                "start": f"{timer.start_hour:02d}:{timer.start_minute:02d}",
                "stop": f"{timer.stop_hour:02d}:{timer.stop_minute:02d}",
                "weekdays": serialize_weekdays(timer.active_days),
            }
            for timer in location.charge_timers
        ],
        "departure_times": [
            {
                "id": departure.id,
                "activated": departure.activated,
                "time": f"{departure.hour:02d}:{departure.minute:02d}",
                "weekdays": serialize_weekdays(departure.active_days),
            }
            for departure in location.departure_times
        ],
    }
