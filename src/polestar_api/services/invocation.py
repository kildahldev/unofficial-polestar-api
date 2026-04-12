"""Invocation service — lock, unlock, climate, honk/flash commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.honkflash import HonkAndFlashRequest, HonkAndFlashResponse, HonkFlashAction
from ..models.invocation import InvocationRequest
from ..models.locks import (
    CarLockRequest,
    CarLockResponse,
    CarUnlockRequest,
    CarUnlockResponse,
    LockAlarmLevel,
    LockFeedback,
    LockType,
    TrunkUnlockResponse,
    UnlockFeedback,
    UnlockType,
)
from ..models.climatization import (
    ClimatizationResponse,
    ClimatizationStartRequest,
    ClimatizationStopRequest,
    HeatingIntensity,
)
from ..models.wakeup import WakeUpReason, WakeUpResponse
from ..models.window import WindowControlRequest, WindowControlType
from ..exceptions import ApiError

if TYPE_CHECKING:
    from ..connection import GrpcConnection

class InvocationServiceClient:
    """Car command service — lock, unlock, climate, honk/flash."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.invocation_svc

    def _request(self) -> InvocationRequest:
        return InvocationRequest(vin=self._vin)

    async def _call(self, method: str, request_bytes: bytes) -> bytes:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        response = None
        async for response in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/{method}",
            request_bytes,
            metadata=metadata,
        ):
            pass
        if response is None:
            raise ApiError(f"{method} returned no invocation response")
        return response

    async def lock(
        self,
        feedback: LockFeedback = LockFeedback.NORMAL,
        alarm_level: LockAlarmLevel = LockAlarmLevel.NORMAL,
    ) -> CarLockResponse:
        lock_type = LockType.LOCK_REDUCED_GUARD if alarm_level == LockAlarmLevel.REDUCED else LockType.LOCK
        req = CarLockRequest(request=self._request(), lock_type=lock_type)
        data = await self._call("Lock", req.to_bytes())
        return CarLockResponse.from_bytes(data)

    async def unlock(self, feedback: UnlockFeedback = UnlockFeedback.NORMAL) -> CarUnlockResponse:
        req = CarUnlockRequest(
            request=self._request(),
            unlock_type=UnlockType.UNLOCK_TYPE_UNSPECIFIED,
        )
        data = await self._call("Unlock", req.to_bytes())
        return CarUnlockResponse.from_bytes(data)

    async def trunk_unlock(self) -> TrunkUnlockResponse:
        req = CarUnlockRequest(
            request=self._request(),
            unlock_type=UnlockType.UNLOCK_TYPE_TRUNK_ONLY,
        )
        data = await self._call("Unlock", req.to_bytes())
        return TrunkUnlockResponse.from_bytes(data)

    async def honk_flash(self, action: HonkFlashAction = HonkFlashAction.FLASH) -> HonkAndFlashResponse:
        req = HonkAndFlashRequest(request=self._request(), honk_flash_type=action)
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
            request=self._request(),
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
        req = ClimatizationStopRequest(request=self._request())
        data = await self._call("ClimatizationStop", req.to_bytes())
        return ClimatizationResponse.from_bytes(data)

    async def wakeup(self, reason: WakeUpReason = WakeUpReason.UNDEFINED) -> WakeUpResponse:
        raise ApiError(
            "WakeUp is not implemented by invocation.InvocationService for the current Polestar backend",
        )

    async def precleaning_start(self) -> bytes:
        """Start pre-cleaning (air quality). Response format TBD."""
        return await self._call("PreCleaningStart", b"")

    async def precleaning_stop(self) -> bytes:
        """Stop pre-cleaning. Response format TBD."""
        return await self._call("PreCleaningStop", b"")

    async def window_control(self, action: WindowControlType) -> ClimatizationResponse:
        req = WindowControlRequest(request=self._request(), windows_control=action)
        data = await self._call("WindowControl", req.to_bytes())
        return ClimatizationResponse.from_bytes(data)
