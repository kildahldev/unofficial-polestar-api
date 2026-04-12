"""Parking climate timer service — schedule climate pre-conditioning."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, decode_packed_varints, encode, encode_message, encode_packed_varints
from ..exceptions import ApiError
from ..models.common import Weekday
from ..models.climatization import HeatingIntensity
from ..models.parking_climate_timer import (
    BatteryPreconditioning,
    ParkingClimateTimer,
    ParkingClimateTimerSettings,
    SeatHeatingSettings,
)
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.ParkingClimateTimerService"
_SUCCESS_STATUSES = {1, 2, 3, 4, 8}
_STREAM_TIMEOUT = 10.0


def _decode_timer(data: bytes) -> ParkingClimateTimer:
    """Decode a single ParkingClimateTimer from raw protobuf bytes."""
    raw = decode(data, {
        1: ("timer_id", "string"),
        2: ("index", "int64"),
        3: ("ready_at", "message"),
        4: ("activated", "bool"),
        5: ("repeat", "bool"),
        6: ("weekdays", "bytes"),
    })
    hour = 0
    minute = 0
    if raw.get("ready_at"):
        time_raw = decode(raw["ready_at"], {1: ("hour", "int64"), 2: ("minute", "int64")})
        hour = time_raw.get("hour", 0)
        minute = time_raw.get("minute", 0)

    weekdays: tuple[Weekday, ...] = ()
    if raw.get("weekdays"):
        wd_bytes = raw["weekdays"]
        if isinstance(wd_bytes, bytes):
            weekdays = tuple(Weekday(v) for v in decode_packed_varints(wd_bytes))

    return ParkingClimateTimer(
        timer_id=raw.get("timer_id", ""),
        index=raw.get("index", 0),
        ready_at_hour=hour,
        ready_at_minute=minute,
        activated=raw.get("activated", False),
        repeat=raw.get("repeat", False),
        weekdays=weekdays,
    )


def _as_list(value: bytes | list[bytes] | None) -> list[bytes]:
    """Return a protobuf field as a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _merge_timers_response(data: bytes) -> list[ParkingClimateTimer]:
    """Decode a GetTimers response, merging pending changes."""
    raw = decode(
        data,
        {
            3: ("timers", "message"),
            4: ("pending_timers", "message"),
            5: ("pending_delete_timers", "message"),
        },
    )

    deleted_ids = {
        timer.timer_id
        for timer in (_decode_timer(item) for item in _as_list(raw.get("pending_delete_timers")))
        if timer.timer_id
    }
    merged: dict[str, ParkingClimateTimer] = {}

    for payload in _as_list(raw.get("timers")):
        timer = _decode_timer(payload)
        if timer.timer_id and timer.timer_id not in deleted_ids:
            merged[timer.timer_id] = timer

    for payload in _as_list(raw.get("pending_timers")):
        timer = _decode_timer(payload)
        if timer.timer_id and timer.timer_id not in deleted_ids:
            merged[timer.timer_id] = timer

    return sorted(merged.values(), key=lambda timer: (timer.index, timer.timer_id))


def _encode_timer(timer: ParkingClimateTimer) -> bytes:
    """Encode a ParkingClimateTimer request payload."""
    ready_at = encode(
        {"hour": (1, "int64"), "minute": (2, "int64")},
        {"hour": timer.ready_at_hour, "minute": timer.ready_at_minute},
    )
    payload = encode(
        {
            "timer_id": (1, "string"),
            "index": (2, "int64"),
            "ready_at": (3, "message"),
            "activated": (4, "bool"),
            "repeat": (5, "bool"),
        },
        {
            "timer_id": timer.timer_id or None,
            "index": timer.index,
            "ready_at": ready_at,
            "activated": timer.activated,
            "repeat": timer.repeat,
        },
    )
    if timer.weekdays:
        payload += encode_packed_varints(6, [int(day) for day in timer.weekdays])
    return payload


def _decode_set_timer_status(data: bytes) -> int:
    """Decode a SetTimers status update and raise on backend errors."""
    raw = decode(
        data,
        {
            1: ("request_id", "string"),
            2: ("vin", "string"),
            3: ("status", "int32"),
            4: ("message", "string"),
        },
    )
    status = raw.get("status", 0)
    if status not in _SUCCESS_STATUSES:
        message = raw.get("message") or "Parking climate timer update failed"
        raise ApiError(message, status_code=status)
    return status


def _decode_delete_status(data: bytes) -> int:
    """Decode a delete response status and raise on backend errors."""
    raw = decode(data, {1: ("status", "int32")})
    status = raw.get("status", 0)
    if status == 0:
        raise ApiError("Parking climate timer delete failed", status_code=status)
    return status


def _decode_seat_heating(data: bytes) -> SeatHeatingSettings:
    """Decode a SeatHeatingIntensity submessage."""
    raw = decode(data, {
        1: ("front_left", "int32"),
        2: ("front_right", "int32"),
        3: ("rear_left", "int32"),
        4: ("rear_right", "int32"),
    })
    return SeatHeatingSettings(
        front_left=HeatingIntensity(raw.get("front_left", 0)),
        front_right=HeatingIntensity(raw.get("front_right", 0)),
        rear_left=HeatingIntensity(raw.get("rear_left", 0)),
        rear_right=HeatingIntensity(raw.get("rear_right", 0)),
    )


def _decode_timer_settings(data: bytes) -> ParkingClimateTimerSettings:
    """Decode a TimerSettings submessage."""
    raw = decode(data, {
        1: ("seat_heating", "message"),
        2: ("steering_wheel", "int32"),
        3: ("temperature", "float"),
        4: ("is_temp_requested", "bool"),
        5: ("battery_preconditioning", "int32"),
    })
    seat_heating = SeatHeatingSettings()
    if raw.get("seat_heating"):
        seat_heating = _decode_seat_heating(raw["seat_heating"])
    return ParkingClimateTimerSettings(
        seat_heating=seat_heating,
        steering_wheel_heating=HeatingIntensity(raw.get("steering_wheel", 0)),
        temperature_celsius=raw.get("temperature", 0.0),
        is_temperature_requested=raw.get("is_temp_requested", False),
        battery_preconditioning=BatteryPreconditioning(raw.get("battery_preconditioning", 0)),
    )


def _decode_timer_settings_response(data: bytes) -> ParkingClimateTimerSettings:
    """Decode a GetTimerSettings response, preferring pending over active."""
    raw = decode(data, {
        1: ("timer_settings", "message"),
        2: ("pending_timer_settings", "message"),
        3: ("updated_at", "int64"),
    })
    # Pending settings override active, same pattern as timer merging
    settings_bytes = raw.get("pending_timer_settings") or raw.get("timer_settings")
    if settings_bytes:
        return _decode_timer_settings(settings_bytes)
    return ParkingClimateTimerSettings()


def _encode_seat_heating(seat: SeatHeatingSettings) -> bytes:
    """Encode a SeatHeatingIntensity submessage."""
    return encode(
        {
            "front_left": (1, "int32"),
            "front_right": (2, "int32"),
            "rear_left": (3, "int32"),
            "rear_right": (4, "int32"),
        },
        {
            "front_left": int(seat.front_left),
            "front_right": int(seat.front_right),
            "rear_left": int(seat.rear_left),
            "rear_right": int(seat.rear_right),
        },
    )


def _encode_timer_settings(settings: ParkingClimateTimerSettings) -> bytes:
    """Encode a TimerSettings submessage."""
    seat_data = _encode_seat_heating(settings.seat_heating)
    return encode(
        {
            "seat_heating": (1, "message"),
            "steering_wheel": (2, "int32"),
            "temperature": (3, "float"),
            "is_temp_requested": (4, "bool"),
            "battery_preconditioning": (5, "int32"),
        },
        {
            "seat_heating": seat_data,
            "steering_wheel": int(settings.steering_wheel_heating),
            "temperature": settings.temperature_celsius,
            "is_temp_requested": settings.is_temperature_requested,
            "battery_preconditioning": int(settings.battery_preconditioning),
        },
    )


def _decode_set_timer_settings_status(data: bytes) -> int:
    """Decode a SetTimerSettings response status."""
    raw = decode(data, {
        1: ("status", "int32"),
        2: ("message", "string"),
    })
    status = raw.get("status", 0)
    if status not in _SUCCESS_STATUSES:
        message = raw.get("message") or "Timer settings update failed"
        raise ApiError(message, status_code=status)
    return status


class ParkingClimateTimerServiceClient:
    """Parking climate timer management (chronos service)."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def _metadata(self) -> dict:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        return metadata

    async def get_timers(self) -> list[ParkingClimateTimer]:
        """Get all parking climate timers."""
        metadata = await self._metadata()
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{_SVC}/GetTimers",
                    wrap_chronos(self._vin),
                    metadata=metadata,
                ):
                    return _merge_timers_response(data)
        except TimeoutError:
            pass
        return []

    async def set_timer(self, timer: ParkingClimateTimer) -> int:
        """Create or update a parking climate timer."""
        payload = encode_message(2, _encode_timer(timer))
        metadata = await self._metadata()
        final_status = 0
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{_SVC}/SetTimers",
                    wrap_chronos(self._vin, payload),
                    metadata=metadata,
                ):
                    final_status = _decode_set_timer_status(data)
        except TimeoutError:
            pass
        return final_status

    async def delete_timer(self, timer_id: str) -> int:
        """Delete a parking climate timer. Returns status code."""
        payload = encode(
            {"timer_id": (2, "string")},
            {"timer_id": timer_id},
        )
        metadata = await self._metadata()
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{_SVC}/DeleteTimer",
                    wrap_chronos(self._vin, payload),
                    metadata=metadata,
                ):
                    return _decode_delete_status(data)
        except TimeoutError:
            pass
        return 0

    async def get_timer_settings(self) -> ParkingClimateTimerSettings:
        """Get the default climate settings for parking climate timers."""
        metadata = await self._metadata()
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{_SVC}/GetTimerSettings",
                    wrap_chronos(self._vin),
                    metadata=metadata,
                ):
                    return _decode_timer_settings_response(data)
        except TimeoutError:
            pass
        return ParkingClimateTimerSettings()

    async def set_timer_settings(self, settings: ParkingClimateTimerSettings) -> int:
        """Set the default climate settings for parking climate timers."""
        payload = encode_message(2, _encode_timer_settings(settings))
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/SetTimerSettings",
            wrap_chronos(self._vin, payload),
            metadata=metadata,
        )
        return _decode_set_timer_settings_status(data)
