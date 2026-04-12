"""Charge now service — start/stop override charge timer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.ChargeNowService"


class ChargeNowServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def _call(self, method: str) -> int:
        """Call a charge now method. Returns response status code."""
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/{method}",
            wrap_chronos(self._vin), metadata=metadata,
        )
        raw = decode(data, {1: ("status", "int32")})
        return raw.get("status", 0)

    async def start(self) -> int:
        """Start charging now (override timer). Returns status code."""
        return await self._call("StartOverrideChargeTimer")

    async def stop(self) -> int:
        """Stop charge now override. Returns status code."""
        return await self._call("StopOverrideChargeTimer")
