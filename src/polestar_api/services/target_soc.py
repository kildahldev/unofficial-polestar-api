"""Target SoC service — get/set battery charge target level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.charging import (
    ChargeTargetLevelSettingType,
    SetTargetSocRequest,
    TargetSocResponse,
)

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.TargetSocService"


class TargetSocServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get(self) -> TargetSocResponse:
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/GetTargetSoc", b"", metadata=metadata,
        )
        return TargetSocResponse.from_bytes(data)

    async def set(
        self,
        level: int,
        setting_type: ChargeTargetLevelSettingType = ChargeTargetLevelSettingType.DAILY,
    ) -> TargetSocResponse:
        req = SetTargetSocRequest(target_level=level, setting_type=setting_type)
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/SetTargetSoc", req.to_bytes(), metadata=metadata,
        )
        return TargetSocResponse.from_bytes(data)
