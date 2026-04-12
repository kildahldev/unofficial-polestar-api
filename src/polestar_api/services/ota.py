"""OTA service — software update info and scheduling."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.ota import CarSoftwareInfo, Scheduler

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_STREAM_TIMEOUT = 10.0


class OtaServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _discovery(self) -> str:
        return self._connection.backend.ota_discovery_svc

    @property
    def _scheduler(self) -> str:
        return self._connection.backend.ota_scheduler_svc

    def _vin_bytes(self) -> bytes:
        return encode({"vin": (1, "string")}, {"vin": self._vin})

    async def _metadata(self) -> dict:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        return metadata

    async def get_software_info(self) -> CarSoftwareInfo | None:
        """Get current software update info (first result from server stream)."""
        req = encode(
            {"vin": (1, "string"), "locale": (2, "string")},
            {"vin": self._vin, "locale": "en"},
        )
        metadata = await self._metadata()
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{self._discovery}/GetSoftwareInfo",
                    req,
                    metadata=metadata,
                ):
                    raw = decode(data, {1: ("info", "message")})
                    if raw.get("info"):
                        return CarSoftwareInfo.from_bytes(raw["info"])
        except TimeoutError:
            pass
        return None

    async def get_schedule(self) -> Scheduler | None:
        """Get current OTA schedule (first result from server stream)."""
        metadata = await self._metadata()
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{self._scheduler}/GetSchedule",
                    self._vin_bytes(),
                    metadata=metadata,
                ):
                    raw = decode(data, {1: ("timer", "message")})
                    if raw.get("timer"):
                        return Scheduler.from_bytes(raw["timer"])
        except TimeoutError:
            pass
        return None

    async def schedule(self, software_id: str, relative_time: int = 0) -> Scheduler | None:
        """Schedule an OTA install. relative_time is seconds from now."""
        req = encode(
            {"vin": (1, "string"), "relative_time": (2, "int32"), "software_id": (3, "string")},
            {"vin": self._vin, "relative_time": relative_time, "software_id": software_id},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._scheduler}/Schedule", req, metadata=metadata,
        )
        raw = decode(data, {1: ("timer", "message")})
        if raw.get("timer"):
            return Scheduler.from_bytes(raw["timer"])
        return None

    async def install_now(self, software_id: str) -> Scheduler | None:
        req = encode(
            {"vin": (1, "string"), "software_id": (2, "string")},
            {"vin": self._vin, "software_id": software_id},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._scheduler}/InstallNow", req, metadata=metadata,
        )
        raw = decode(data, {1: ("timer", "message")})
        if raw.get("timer"):
            return Scheduler.from_bytes(raw["timer"])
        return None

    async def cancel_schedule(self, software_id: str) -> Scheduler | None:
        req = encode(
            {"vin": (1, "string"), "software_id": (2, "string")},
            {"vin": self._vin, "software_id": software_id},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._scheduler}/CancelSchedule", req, metadata=metadata,
        )
        raw = decode(data, {1: ("timer", "message")})
        if raw.get("timer"):
            return Scheduler.from_bytes(raw["timer"])
        return None
