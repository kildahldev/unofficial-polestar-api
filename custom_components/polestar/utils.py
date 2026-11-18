"""Utility helpers for the Polestar integration."""

from __future__ import annotations

from datetime import UTC, datetime, time as dt_time
from enum import IntEnum
from typing import Any

from homeassistant.util import dt as dt_util

from polestar_api.models.charge_location import ChargeLocation
from polestar_api.models.exterior import AlarmStatus
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


def state_icon(is_on: bool | None, icon_on: str | None, icon_off: str | None, default: str | None) -> str | None:
    """Icon that follows a binary state; an unknown state shows the "off" icon."""
    if icon_on is None and icon_off is None:
        return default
    return icon_on if is_on else icon_off


def climate_end_time(climate) -> float | None:
    """When the running climate ends (seconds since the epoch), or ``None`` if it is not running."""
    if climate is None or not climate.is_active or not climate.ending_at:
        return None
    return float(climate.ending_at)


def climate_minutes_remaining(climate, now: float) -> int | None:
    """Minutes left of a running climate, counted from its end time when the car reports one.

    The car's own "runtime left" stays at the full duration while the climate runs.
    """
    if climate is None:
        return None
    end = climate_end_time(climate)
    if end is not None:
        return max(0, -int((now - end) // 60))
    return climate.time_remaining


def is_polestar_4(model_name: str | None, vin: str) -> bool:
    """Return True for a Polestar 4.

    Falls back to the VIN prefix because the model name is missing when vehicle
    discovery is rejected and the integration only knows the configured VIN.
    """
    if model_name:
        return model_name.casefold().replace("polestar", "").strip() == "4"
    return vin.upper().startswith("YSM4")


def normalise_steering_wheel_option(option: str) -> str:
    """Steering wheel heating is on/off on a Polestar 4: the car runs any heated level as level3."""
    return "level3" if option in ("level1", "level2") else option


def climate_timer_label(slot: int, max_timers: int | None, prefix: str) -> str:
    """Name of a climate timer slot, without a number when the car has only one timer."""
    return prefix if max_timers == 1 else f"{prefix} {slot + 1}"


_CLIMATE_ACTIONS = {
    "heating": "heating",
    "cooling": "cooling",
    "cooling_fast": "cooling",
    "ventilation_only": "ventilating",
    "not_required": "not_required",
}


def climate_action(climate: Any) -> str | None:
    """Heating, cooling, ventilating or not_required (same words as the Volvo integration)."""
    name = enum_name(getattr(climate, "heat_or_cool_action", None))
    return _CLIMATE_ACTIONS.get(name) if name else None


def climate_attributes(climate: Any) -> dict[str, Any]:
    """Attributes for the Climate switch, matching the Volvo integration's names."""
    if climate is None:
        return {}
    attrs: dict[str, Any] = {
        "runtime_left_minutes": getattr(climate, "time_remaining", None),
        "start_reason": enum_name(getattr(climate, "request_type", None)),
    }
    action = climate_action(climate)
    if action:
        attrs["action"] = action
    target = getattr(climate, "target_temperature_celsius", None)
    if target is not None:
        attrs["target_temperature"] = target
    return attrs


def weather_attributes(weather: Any) -> dict[str, Any]:
    """When the weather service says the outside temperature was taken (it is a lookup at the car's location)."""
    millis = getattr(weather, "timestamp_epoch_millis", 0) if weather else 0
    if not millis:
        return {}
    return {
        "report_time": datetime.fromtimestamp(millis / 1000, tz=dt_util.UTC).isoformat(),
        "source": "weather service",
    }


def charge_timer_active(charge_timer: Any) -> bool | None:
    """Whether the charge timer is on. A car with no timer set sends none: that is off, not unknown.

    None (unknown) only when the car has not answered at all, so the switch never shows both
    on and off buttons because of an unset timer.
    """
    if charge_timer is None:
        return None
    timer = getattr(charge_timer, "timer", None)
    if timer is None:
        return False
    return bool(getattr(timer, "activated", False))


def entry_title(model_name: str | None, model_year: int | None, vin: str) -> str:
    """Config entry title in the Volvo integration's style: "Polestar 2 2026" (VIN when the year is unknown)."""
    model = model_name or "Polestar"
    return f"{model} {model_year}" if model_year else f"{model} {vin}"


def flatten_attributes(data: Any, prefix: str = "") -> dict[str, Any]:
    """Turn nested data into flat snake_case attributes so Home Assistant lists them one per row.

    Empty values are left out and lists of simple values become one comma-separated string.
    """
    import re

    out: dict[str, Any] = {}
    if not isinstance(data, dict):
        return out
    for key, value in data.items():
        name = re.sub(r"[^0-9a-z]+", "_", re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", f"{prefix}{key}").lower()).strip("_")
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, (bytes, bytearray)):
            # Packed lists (such as light warnings) arrive as raw bytes, which Home Assistant cannot store as JSON.
            out[name] = ", ".join(str(b) for b in value)
        elif isinstance(value, dict):
            out.update(flatten_attributes(value, f"{name}_"))
        elif isinstance(value, (list, tuple)):
            out[name] = ", ".join(str(item) for item in value)
        else:
            out[name] = value
    return out


def driving(usage_mode: Any) -> bool | None:
    """True only while the car reports Driving (not merely recently used); None when it says nothing."""
    name = enum_name(usage_mode)
    if name is None:
        return None
    return name == "driving"


def in_use(availability: Any) -> bool | None:
    """Is the car being used right now (so a remote command cannot reach it)?

    True when the car reports Driving, or reports "unavailable because the car is in use": the Polestar app
    shows "In use" from that reason. None when there is no availability reading.
    """
    if availability is None:
        return None
    if driving(getattr(availability, "usage_mode", None)) is True:
        return True
    if _reason_key(availability) == "CAR_IN_USE" and not getattr(availability, "is_available", True):
        return True
    return driving(getattr(availability, "usage_mode", None))


def level_problem(warning: Any) -> bool | None:
    """A fluid-level warning as a problem flag: off for "no warning", on for too low / critically low."""
    name = enum_name(warning)
    if name is None:
        return None
    return name != "no_warning"


_LIGHT_LABELS = {
    "turn_indication": "turn indicator",
    "position_light": "position light",
    "high_beam": "high beam",
    "low_beam": "low beam",
    "daytime_running_light": "daytime running light",
    "fog_light": "fog light",
    "brake_light": "brake light",
    "registration_plate_light": "registration plate light",
    "side_mark_lights": "side marker lights",
}


def light_attributes(health: Any) -> dict[str, str]:
    """Status of every light the car reports: ``ok``, ``failure`` or ``unknown`` (one attribute per light)."""
    out: dict[str, str] = {}
    schema = getattr(health, "_schema", None) or {}
    for field in schema.values():
        if not field.endswith("_warning"):
            continue
        base = field[: -len("_warning")]
        label = next((label for prefix, label in _LIGHT_LABELS.items() if base.startswith(prefix)), None)
        if label is None:
            continue
        position = base[len(next(p for p in _LIGHT_LABELS if base.startswith(p))) :].strip("_").replace("_", " ")
        name = f"{position} {label}".strip().replace(" ", "_")
        value = getattr(health, field, None)
        state = enum_name(value)
        out[name] = "ok" if state == "no_warning" else "unknown" if state is None else state
    return out


def poll_is_active(data: Any) -> bool:
    """Is something happening that deserves the faster poll: charging, driving, or the climate running?"""
    battery = getattr(data, "battery", None)
    if battery is not None and getattr(battery, "is_charging", False):
        return True
    climate = getattr(data, "climate", None)
    if climate is not None and getattr(climate, "is_active", False):
        return True
    availability = getattr(data, "availability", None)
    return in_use(availability) is True


def alarm_triggered(exterior: Any) -> bool | None:
    """True when any door, the hood or the tailgate reports a triggered alarm.

    The car reports the alarm per closure and the Polestar 2 sends none, so a car that has reported its doors but says
    nothing about an alarm counts as not triggered (shown as OK). None only before any exterior data has arrived.
    """
    if exterior is None:
        return None
    parts = []
    if exterior.doors is not None:
        parts.extend((exterior.doors.front_left, exterior.doors.front_right, exterior.doors.rear_left, exterior.doors.rear_right))
    if exterior.hood is not None:
        parts.append(exterior.hood.status)
    if exterior.tailgate is not None:
        parts.append(exterior.tailgate.status)
    states = [p.alarm_status for p in parts if p is not None and p.alarm_status != AlarmStatus.UNSPECIFIED]
    return any(state == AlarmStatus.TRIGGERED for state in states)


# The car's reasons for being unavailable, in plain words.
_REASON_TEXT = {
    "NO_INTERNET": "the car has no mobile internet (weak signal?)",
    "POWER_SAVING_MODE": "the car is in power saving mode",
    "CAR_IN_USE": "the car is in use",
    "OTA_INSTALLATION_IN_PROGRESS": "a software update is installing",
    "STOLEN_VEHICLE_TRACKING_IN_PROGRESS": "stolen vehicle tracking is active",
    "SERVICE_MODE_ACTIVE": "the car is in service mode",
}
# Reasons for which a command cannot reach the car (it is being driven, has no internet, is updating, is in
# service or tracking a theft). Power saving is left out: the car wakes for a command.
_COMMAND_BLOCKING_REASONS = frozenset(
    {"CAR_IN_USE", "NO_INTERNET", "OTA_INSTALLATION_IN_PROGRESS", "STOLEN_VEHICLE_TRACKING_IN_PROGRESS", "SERVICE_MODE_ACTIVE"}
)


def _reason_key(availability: Any) -> str:
    name = getattr(getattr(availability, "unavailable_reason", None), "name", "") or ""
    return "" if name == "UNSPECIFIED" else name


def last_seen(data: Any) -> datetime | None:
    """The newest car-side time in the data Polestar sent (the car's own time, not our poll time)."""
    seconds = []
    for part, attr in (
        ("battery", "timestamp"), ("odometer", "timestamp"), ("availability", "timestamp"),
        ("health", "timestamp"), ("precleaning", "timestamp"), ("connectivity", "updated_timestamp"),
    ):
        stamp = getattr(getattr(data, part, None), attr, None)
        value = getattr(stamp, "seconds", 0)
        if isinstance(value, int) and value > 0:
            seconds.append(value)
    return datetime.fromtimestamp(max(seconds), UTC) if seconds else None


def connection_text(data: Any, local_time: Any) -> str:
    """One sentence about whether commands can reach the car (``local_time(dt)`` formats a time as HH:MM)."""
    availability = getattr(data, "availability", None)
    if availability is None:
        return "Unknown: Polestar does not say whether the car is online."
    if availability.is_available:
        return "Online: the car can receive commands."
    seen = last_seen(data)
    when = f" since {local_time(seen)}" if seen is not None else ""
    why = _REASON_TEXT.get(_reason_key(availability), "no connection to the car")
    return f"Offline{when}: {why}. Commands may not reach the car until it is online again."


def command_blocker(data: Any, local_time: Any) -> str | None:
    """Why a command should not be sent right now, or None when it can go."""
    availability = getattr(data, "availability", None)
    if availability is None or availability.is_available:
        return None
    key = _reason_key(availability)
    if key not in _COMMAND_BLOCKING_REASONS:
        return None
    seen = last_seen(data)
    when = f" since {local_time(seen)}" if seen is not None else ""
    state = "in use" if key == "CAR_IN_USE" else f"offline{when}"
    return f"The car is {state} ({_REASON_TEXT[key]}). Nothing was sent. Try again when it is available."
