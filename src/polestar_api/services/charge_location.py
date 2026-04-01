"""Charge location service — saved charging locations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, decode_packed_varints, encode
from ..models.common import Weekday
from ..models.charge_location import (
    ChargeLocation,
    ChargeLocationDepartureTime,
    ChargeLocationTimer,
    LocationType,
    OptimisedChargingType,
)

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.ChargeLocationService"


def _decode_daily_time(data: bytes) -> tuple[int, int]:
    """Decode DailyTime message into (hour, minute)."""
    raw = decode(data, {1: ("hour", "int64"), 2: ("minute", "int64")})
    return raw.get("hour", 0), raw.get("minute", 0)


def _decode_weekdays(data: bytes | None) -> tuple[Weekday, ...]:
    """Decode packed repeated Weekday field."""
    if not data or not isinstance(data, bytes):
        return ()
    return tuple(Weekday(v) for v in decode_packed_varints(data))


def _decode_charge_timer(data: bytes) -> ChargeLocationTimer:
    raw = decode(data, {
        1: ("id", "string"),
        2: ("activated", "bool"),
        3: ("start", "message"),
        4: ("stop", "message"),
        5: ("active_days", "bytes"),
    })
    sh, sm = _decode_daily_time(raw["start"]) if raw.get("start") else (0, 0)
    eh, em = _decode_daily_time(raw["stop"]) if raw.get("stop") else (0, 0)
    return ChargeLocationTimer(
        id=raw.get("id", ""),
        activated=raw.get("activated", False),
        start_hour=sh, start_minute=sm,
        stop_hour=eh, stop_minute=em,
        active_days=_decode_weekdays(raw.get("active_days")),
    )


def _decode_departure_time(data: bytes) -> ChargeLocationDepartureTime:
    raw = decode(data, {
        1: ("id", "string"),
        2: ("activated", "bool"),
        3: ("departure_time", "message"),
        4: ("active_days", "bytes"),
    })
    h, m = _decode_daily_time(raw["departure_time"]) if raw.get("departure_time") else (0, 0)
    return ChargeLocationDepartureTime(
        id=raw.get("id", ""),
        activated=raw.get("activated", False),
        hour=h, minute=m,
        active_days=_decode_weekdays(raw.get("active_days")),
    )


def _decode_charge_location(data: bytes) -> ChargeLocation:
    raw = decode(data, {
        2: ("location_id", "string"),
        3: ("location_alias", "string"),
        4: ("coordinate", "message"),
        5: ("amp_limit", "int64"),
        6: ("minimum_soc", "int64"),
        7: ("is_optimised_charging_enabled", "bool"),
        8: ("is_bidirectional_charging_enabled", "bool"),
        9: ("available_optimised_charging", "int64"),
        10: ("charge_timers", "message"),
        11: ("departure_times", "message"),
        12: ("location_type", "int64"),
    })
    lat, lon = 0.0, 0.0
    if raw.get("coordinate"):
        coord = decode(raw["coordinate"], {1: ("lon", "double"), 2: ("lat", "double")})
        lon = coord.get("lon", 0.0) if isinstance(coord.get("lon"), float) else 0.0
        lat = coord.get("lat", 0.0) if isinstance(coord.get("lat"), float) else 0.0

    timers_data = raw.get("charge_timers")
    timers: tuple[ChargeLocationTimer, ...] = ()
    if timers_data:
        if not isinstance(timers_data, list):
            timers_data = [timers_data]
        timers = tuple(_decode_charge_timer(t) for t in timers_data)

    departures_data = raw.get("departure_times")
    departures: tuple[ChargeLocationDepartureTime, ...] = ()
    if departures_data:
        if not isinstance(departures_data, list):
            departures_data = [departures_data]
        departures = tuple(_decode_departure_time(d) for d in departures_data)

    return ChargeLocation(
        location_id=raw.get("location_id", ""),
        location_alias=raw.get("location_alias", ""),
        latitude=lat,
        longitude=lon,
        amp_limit=raw.get("amp_limit", 0),
        minimum_soc=raw.get("minimum_soc", 0),
        is_optimised_charging_enabled=raw.get("is_optimised_charging_enabled", False),
        is_bidirectional_charging_enabled=raw.get("is_bidirectional_charging_enabled", False),
        available_optimised_charging=OptimisedChargingType(raw.get("available_optimised_charging", 0)),
        location_type=LocationType(raw.get("location_type", 0)),
        charge_timers=timers,
        departure_times=departures,
    )


class ChargeLocationServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def _metadata(self) -> dict:
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        return metadata

    async def get_locations(self) -> list[ChargeLocation]:
        """Get saved charge locations."""
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetChargeLocations",
            b"",
            metadata=metadata,
        )
        raw = decode(data, {3: ("locations", "message")})
        locations = raw.get("locations")
        if locations is None:
            return []
        if not isinstance(locations, list):
            locations = [locations]
        return [_decode_charge_location(loc) for loc in locations]

    async def is_at_location(self) -> dict:
        """Check if car is at a saved charge location.

        Returns dict with 'location_id' (str) and 'arrived_at' (int timestamp).
        """
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/isAtALocation",
            b"",
            metadata=metadata,
        )
        raw = decode(data, {
            1: ("status", "int32"),
            2: ("location_id", "string"),
            3: ("arrived_at", "int64"),
        })
        return raw

    async def create_at_car_location(
        self,
        alias: str,
        amp_limit: int = 0,
        minimum_soc: int = 0,
        optimised_charging: bool = False,
    ) -> ChargeLocation | None:
        """Create a new charge location at the car's current position."""
        req = encode(
            {
                "alias": (2, "string"),
                "amp_limit": (3, "int32"),
                "minimum_soc": (4, "int32"),
                "optimised": (5, "bool"),
            },
            {
                "alias": alias,
                "amp_limit": amp_limit,
                "minimum_soc": minimum_soc,
                "optimised": optimised_charging,
            },
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/CreateAtTheCarLocation",
            req,
            metadata=metadata,
        )
        raw = decode(data, {
            1: ("status", "int32"),
            3: ("location", "message"),
        })
        if raw.get("location"):
            return _decode_charge_location(raw["location"])
        return None

    async def update_alias(self, location_id: str, alias: str) -> int:
        """Update a charge location's alias. Returns status code."""
        req = encode(
            {"location_id": (2, "string"), "alias": (3, "string")},
            {"location_id": location_id, "alias": alias},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/UpdateAlias", req, metadata=metadata,
        )
        raw = decode(data, {1: ("status", "int32")})
        return raw.get("status", 0)

    async def update_amp_limit(self, location_id: str, amp_limit: int) -> int:
        """Update a charge location's amp limit. Returns status code."""
        req = encode(
            {"location_id": (2, "string"), "amp_limit": (3, "int32")},
            {"location_id": location_id, "amp_limit": amp_limit},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/UpdateAmpLimit", req, metadata=metadata,
        )
        raw = decode(data, {1: ("status", "int32")})
        return raw.get("status", 0)

    async def update_minimum_soc(self, location_id: str, minimum_soc: int) -> int:
        """Update a charge location's minimum SOC. Returns status code."""
        req = encode(
            {"location_id": (2, "string"), "minimum_soc": (3, "int32")},
            {"location_id": location_id, "minimum_soc": minimum_soc},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/UpdateMinimumSoc", req, metadata=metadata,
        )
        raw = decode(data, {1: ("status", "int32")})
        return raw.get("status", 0)

    async def update_optimised_charging(self, location_id: str, enabled: bool) -> int:
        """Enable or disable optimised charging at a location. Returns status code."""
        req = encode(
            {"location_id": (2, "string"), "enabled": (3, "bool")},
            {"location_id": location_id, "enabled": enabled},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/UpdateOptimizedSetting", req, metadata=metadata,
        )
        raw = decode(data, {1: ("status", "int32")})
        return raw.get("status", 0)

    async def delete_location(self, location_id: str) -> int:
        """Delete a saved charge location."""
        req = encode(
            {"location_id": (1, "string")},
            {"location_id": location_id},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/DeleteLocation",
            req,
            metadata=metadata,
        )
        raw = decode(data, {1: ("status", "int32")})
        return raw.get("status", 0)
