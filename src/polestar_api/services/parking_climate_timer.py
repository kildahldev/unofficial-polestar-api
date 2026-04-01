"""Parking climate timer service — schedule climate pre-conditioning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, decode_packed_varints, encode
from ..models.common import Weekday
from ..models.parking_climate_timer import ParkingClimateTimer

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.ParkingClimateTimerService"


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


class ParkingClimateTimerServiceClient:
    """Parking climate timer management (chronos service)."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def _metadata(self) -> dict:
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        return metadata

    async def get_timers(self) -> list[ParkingClimateTimer]:
        """Get all parking climate timers."""
        metadata = await self._metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{_SVC}/GetTimers",
            b"",
            metadata=metadata,
        ):
            raw = decode(data, {3: ("timers", "message")})
            timers_data = raw.get("timers")
            if timers_data is None:
                return []
            if not isinstance(timers_data, list):
                timers_data = [timers_data]
            return [_decode_timer(t) for t in timers_data]
        return []

    async def delete_timer(self, timer_id: str) -> int:
        """Delete a parking climate timer. Returns status code."""
        req = encode(
            {"timer_id": (2, "string")},
            {"timer_id": timer_id},
        )
        metadata = await self._metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{_SVC}/DeleteTimer",
            req,
            metadata=metadata,
        ):
            raw = decode(data, {1: ("status", "int32")})
            return raw.get("status", 0)
        return 0
