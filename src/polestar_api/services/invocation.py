"""Invocation service — lock, unlock, climate, honk/flash commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.common import ResponseStatus
from ..models.exterior import ExteriorStatus
from ..models.honkflash import HonkAndFlashRequest, HonkAndFlashResponse, HonkFlashAction
from ..models.locks import (
    CarLockRequest,
    CarLockResponse,
    CarUnlockRequest,
    CarUnlockResponse,
    LockAlarmLevel,
    LockFeedback,
    TrunkUnlockRequest,
    TrunkUnlockResponse,
    UnlockFeedback,
)
from ..models.climatization import (
    ClimatizationResponse,
    ClimatizationStartRequest,
    HeatingIntensity,
)
from ..models.wakeup import WakeUpRequest, WakeUpReason, WakeUpResponse
from ..models.window import WindowControlRequest, WindowControlType

if TYPE_CHECKING:
    from ..connection import GrpcConnection

# C3 invocation service
_SVC = "/invocation.InvocationService"


class InvocationServiceClient:
    """Car command service — lock, unlock, climate, honk/flash."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def _call(self, method: str, request_bytes: bytes) -> bytes:
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        return await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/{method}",
            request_bytes,
            metadata=metadata,
        )

    async def lock(
        self,
        feedback: LockFeedback = LockFeedback.NORMAL,
        alarm_level: LockAlarmLevel = LockAlarmLevel.NORMAL,
    ) -> CarLockResponse:
        req = CarLockRequest(feedback=feedback, alarm_level=alarm_level)
        data = await self._call("Lock", req.to_bytes())
        return CarLockResponse.from_bytes(data)

    async def unlock(self, feedback: UnlockFeedback = UnlockFeedback.NORMAL) -> CarUnlockResponse:
        req = CarUnlockRequest(feedback=feedback)
        data = await self._call("Unlock", req.to_bytes())
        return CarUnlockResponse.from_bytes(data)

    async def trunk_unlock(self) -> TrunkUnlockResponse:
        req = TrunkUnlockRequest()
        data = await self._call("TrunkUnlock", req.to_bytes())
        return TrunkUnlockResponse.from_bytes(data)

    async def honk_flash(self, action: HonkFlashAction = HonkFlashAction.FLASH) -> HonkAndFlashResponse:
        req = HonkAndFlashRequest(action=action)
        data = await self._call("HonkFlash", req.to_bytes())
        return HonkAndFlashResponse.from_bytes(data)

    async def climatization_start(
        self,
        temperature: float = 0.0,
        front_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        front_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        rear_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        rear_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        steering_wheel: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
    ) -> ClimatizationResponse:
        req = ClimatizationStartRequest(
            compartment_temperature_celsius=temperature,
            front_left_seat=front_left_seat,
            front_right_seat=front_right_seat,
            rear_left_seat=rear_left_seat,
            rear_right_seat=rear_right_seat,
            steering_wheel=steering_wheel,
        )
        data = await self._call("ClimatizationStart", req.to_bytes())
        return ClimatizationResponse.from_bytes(data)

    async def climatization_stop(self) -> ClimatizationResponse:
        data = await self._call("ClimatizationStop", b"")
        return ClimatizationResponse.from_bytes(data)

    async def wakeup(self, reason: WakeUpReason = WakeUpReason.UNDEFINED) -> WakeUpResponse:
        req = WakeUpRequest(reason=reason)
        data = await self._call("WakeUp", req.to_bytes())
        return WakeUpResponse.from_bytes(data)

    async def precleaning_start(self) -> bytes:
        """Start pre-cleaning (air quality). Response format TBD."""
        return await self._call("PreCleaningStart", b"")

    async def precleaning_stop(self) -> bytes:
        """Stop pre-cleaning. Response format TBD."""
        return await self._call("PreCleaningStop", b"")

    async def window_control(self, action: WindowControlType) -> ClimatizationResponse:
        req = WindowControlRequest(windows_control=action)
        data = await self._call("WindowControl", req.to_bytes())
        return ClimatizationResponse.from_bytes(data)
