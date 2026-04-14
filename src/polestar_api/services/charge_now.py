"""Charge now service — start/stop override charge timer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

class ChargeNowServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.charge_now_svc

    async def _call(self, method: str) -> int:
        """Call a charge now method. Returns response status code."""
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._svc}/{method}",
            wrap_chronos(self._vin), metadata=metadata,
        )
        # Unwrap chronos envelope — field 3 is the actual payload
        raw = decode(data)
        payload = raw.get(3)
        if isinstance(payload, bytes):
            inner = decode(payload, {1: ("status", "int32")})
            return inner.get("status", 0)
        return 0

    async def start(self) -> int:
        """Start charging now (override timer). Returns status code."""
        return await self._call("StartOverrideChargeTimer")

    async def stop(self) -> int:
        """Stop charge now override. Returns status code."""
        return await self._call("StopOverrideChargeTimer")
