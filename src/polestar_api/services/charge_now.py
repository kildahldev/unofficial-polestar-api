"""Charge now service — start/stop override charge timer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.common import CHRONOS_SUCCESS_STATES, ChronosStatus, ResponseStatusCode
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
        raw = decode(data)
        # Some backends return the response status directly at field 1 (e.g.
        # 08 02). Keep the existing status-code contract for HA's command handler.
        status = raw.get(1)
        if isinstance(status, int):
            return status

        payload = raw.get(3)
        if isinstance(payload, bytes):
            inner = decode(payload, {1: ("status", "int32")})
            status = inner.get("status", 0)
            return status if isinstance(status, int) else 0

        # The flat Chronos variant uses field 3 for a delivery lifecycle, which
        # must be normalized rather than confused with ResponseStatusCode.
        if isinstance(payload, int):
            try:
                lifecycle = ChronosStatus(payload)
            except ValueError:
                lifecycle = ChronosStatus.UNKNOWN_ERROR
            return (
                ResponseStatusCode.SUCCESS
                if lifecycle in CHRONOS_SUCCESS_STATES
                else ResponseStatusCode.ERROR
            )
        return ResponseStatusCode.UNDEFINED

    async def start(self) -> int:
        """Start charging now (override timer). Returns status code."""
        return await self._call("StartOverrideChargeTimer")

    async def stop(self) -> int:
        """Stop charge now override. Returns status code."""
        return await self._call("StopOverrideChargeTimer")
