"""Parking climatization service — climate status."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.climate import (
    ClimatizationInfo,
    ClimatizationRequestType,
    ClimatizationRunningStatus,
    HeatOrCoolAction,
)
from ..models.common import VehicleRequest

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_RESPONSE_SCHEMA = {3: ("climate", "message")}


class ClimateServiceClient:
    """Parking climatization status service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.climate_svc

    @staticmethod
    def _map_running_status(value: int | None) -> ClimatizationRunningStatus:
        mapping = {
            1: ClimatizationRunningStatus.ACTIVE,
            2: ClimatizationRunningStatus.IDLE,
            3: ClimatizationRunningStatus.START_ATTEMPT,
        }
        return mapping.get(value, ClimatizationRunningStatus.UNDEFINED)

    @staticmethod
    def _map_request_type(value: int | None) -> ClimatizationRequestType:
        mapping = {
            1: ClimatizationRequestType.NOW_FROM_HMI,
            2: ClimatizationRequestType.NOW_FROM_REMOTE,
            3: ClimatizationRequestType.TIMER,
            4: ClimatizationRequestType.NO_REQUEST,
        }
        return mapping.get(value, ClimatizationRequestType.UNDEFINED)

    @staticmethod
    def _infer_heat_or_cool_action(raw: dict) -> HeatOrCoolAction:
        if raw.get(6):
            return HeatOrCoolAction.VENTILATION_ONLY

        current_temp = raw.get(7)
        requested_temp = raw.get(8)
        if not isinstance(current_temp, (int, float)) or not isinstance(requested_temp, (int, float)):
            return HeatOrCoolAction.UNDEFINED
        if requested_temp > current_temp:
            return HeatOrCoolAction.HEATING
        if requested_temp < current_temp:
            return HeatOrCoolAction.COOLING
        return HeatOrCoolAction.NOT_REQUIRED

    @classmethod
    def _parse_digital_twin(cls, climate_bytes: bytes) -> ClimatizationInfo:
        raw = decode(climate_bytes)
        return ClimatizationInfo(
            running_status=cls._map_running_status(raw.get(2)),
            request_type=cls._map_request_type(raw.get(15)),
            time_remaining=int(raw.get(3, 0) or 0),
            heat_or_cool_action=cls._infer_heat_or_cool_action(raw),
        )

    @classmethod
    def _parse(cls, data: bytes) -> ClimatizationInfo | None:
        raw = decode(data, _RESPONSE_SCHEMA)
        if raw.get("climate"):
            climate_bytes = raw["climate"]
            payload = decode(climate_bytes)
            if isinstance(payload.get(1), bytes):
                return cls._parse_digital_twin(climate_bytes)
            return ClimatizationInfo.from_bytes(climate_bytes)
        return None

    async def get_latest(self) -> ClimatizationInfo | None:
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLatestParkingClimatization",
            request.to_bytes(),
            metadata=metadata,
        )
        return self._parse(data)

    async def stream(self) -> AsyncIterator[ClimatizationInfo]:
        """Stream parking climatization status updates."""
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetParkingClimatization",
            request.to_bytes(),
            metadata=metadata,
        ):
            status = self._parse(data)
            if status is not None:
                yield status
