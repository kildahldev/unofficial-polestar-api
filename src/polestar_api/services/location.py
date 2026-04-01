"""Location service — last known/parked location."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.common import Location

if TYPE_CHECKING:
    from ..connection import GrpcConnection

# C3 Digital Twin Layer location service
_SVC = "/dtlinternet.DtlInternetService"


class LocationServiceClient:
    """Vehicle location service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def _call(self, method: str) -> bytes:
        from ..models.battery import GetBatteryRequest
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        return await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/{method}",
            request.to_bytes(),
            metadata=metadata,
        )

    async def get_last_known(self) -> Location:
        from ..codec import decode
        data = await self._call("GetLastKnownLocation")
        raw = decode(data, {2: ("location", "message")})
        if raw.get("location"):
            return Location.from_bytes(raw["location"])
        return Location()

    async def get_last_parked(self) -> Location:
        from ..codec import decode
        data = await self._call("GetLastParkedLocation")
        raw = decode(data, {2: ("location", "message")})
        if raw.get("location"):
            return Location.from_bytes(raw["location"])
        return Location()

    async def stream_last_known(self) -> AsyncIterator[Location]:
        from ..codec import decode
        from ..models.battery import GetBatteryRequest
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{_SVC}/StreamLastKnownLocations",
            request.to_bytes(),
            metadata=metadata,
        ):
            raw = decode(data, {2: ("location", "message")})
            if raw.get("location"):
                yield Location.from_bytes(raw["location"])

    async def stream_last_parked(self) -> AsyncIterator[Location]:
        from ..codec import decode
        from ..models.battery import GetBatteryRequest
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{_SVC}/StreamLastParkedLocations",
            request.to_bytes(),
            metadata=metadata,
        ):
            raw = decode(data, {2: ("location", "message")})
            if raw.get("location"):
                yield Location.from_bytes(raw["location"])
