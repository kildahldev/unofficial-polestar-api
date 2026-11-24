"""Charge now service — start/stop override charge timer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.common import ResponseStatusCode
from .chronos import wrap_chronos

_CHARGE_NOW_SUCCESS = 1  # chronos ResponseStatus.SUCCESS

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
        # Start/StopOverrideChargeTimerResponse is a single field: 1 = status,
        # using the chronos ResponseStatus enum (UNKNOWN_ERROR 0, SUCCESS 1,
        # VALIDATION_ERROR 2, INTERNAL_ERROR 3, NOT_FOUND 4) on both C3 and PCCS.
        # That enum is not ResponseStatusCode (where 2 means WARNING and counts
        # as success), so map it: only SUCCESS succeeds, everything else is an error.
        status = decode(data, {1: ("status", "int32")}).get("status")
        if not isinstance(status, int):
            return ResponseStatusCode.UNDEFINED
        if status == _CHARGE_NOW_SUCCESS:
            return ResponseStatusCode.SUCCESS
        return ResponseStatusCode.ERROR

    async def start(self) -> int:
        """Start charging now (override timer). Returns status code."""
        return await self._call("StartOverrideChargeTimer")

    async def stop(self) -> int:
        """Stop charge now override. Returns status code."""
        return await self._call("StopOverrideChargeTimer")
