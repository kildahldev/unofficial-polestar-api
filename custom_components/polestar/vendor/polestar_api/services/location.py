"""Location service — last known/parked location."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.common import Coordinate, Location, Timestamp

if TYPE_CHECKING:
    from ..connection import GrpcConnection


def _vin_request(vin: str) -> bytes:
    """Encode a location request (VIN at field 1)."""
    return encode({"vin": (1, "string")}, {"vin": vin})


def _parse_compact_location(data: bytes) -> Location:
    raw = decode(data)
    timestamp = raw.get(3)
    if isinstance(timestamp, bytes):
        timestamp = Timestamp.from_bytes(timestamp)
    elif isinstance(timestamp, int):
        timestamp = Timestamp(seconds=int(timestamp))
    else:
        timestamp = None

    return Location(
        timestamp=timestamp,
        coordinate=Coordinate(
            longitude=float(raw.get(1, 0.0) or 0.0),
            latitude=float(raw.get(2, 0.0) or 0.0),
        ),
    )


def _parse_location_message(data: bytes) -> Location:
    raw = decode(data)

    nested_location = raw.get(5)
    if isinstance(nested_location, bytes):
        return _parse_compact_location(nested_location)

    nested_location = raw.get(2)
    if isinstance(nested_location, bytes):
        return _parse_compact_location(nested_location)

    longitude = raw.get(2)
    latitude = raw.get(3)
    timestamp = raw.get(4)
    if isinstance(longitude, float) and isinstance(latitude, float):
        return Location(
            timestamp=Timestamp(seconds=int(timestamp or 0)),
            coordinate=Coordinate(longitude=longitude, latitude=latitude),
        )

    return Location()


class LocationServiceClient:
    """Vehicle location service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.location_svc

    async def _metadata(self) -> dict[str, str]:
        return await self._connection.get_metadata(self._vin)

    async def get_last_known(self) -> Location:
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLastKnownLocation",
            _vin_request(self._vin),
            metadata=metadata,
        )
        return _parse_location_message(data)

    async def get_last_parked(self) -> Location:
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLastParkedLocation",
            _vin_request(self._vin),
            metadata=metadata,
        )
        return _parse_location_message(data)

    async def stream_last_known(self) -> AsyncIterator[Location]:
        metadata = await self._metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/StreamLastKnownLocations",
            _vin_request(self._vin),
            metadata=metadata,
        ):
            yield _parse_location_message(data)

    async def stream_last_parked(self) -> AsyncIterator[Location]:
        metadata = await self._metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/StreamLastParkedLocations",
            _vin_request(self._vin),
            metadata=metadata,
        ):
            yield _parse_location_message(data)
