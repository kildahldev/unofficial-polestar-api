"""Invocation service — lock, unlock, climate, windows, pre-cleaning, honk/flash."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.honkflash import HonkAndFlashRequest, HonkAndFlashResponse, HonkFlashAction
from ..models.invocation import InvocationEnvelope, InvocationRequest, InvocationResponse
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
from ..models.precleaning import PreCleaningRequest
from ..models.wakeup import WakeUpReason, WakeUpResponse
from ..models.window import WindowControlRequest, WindowControlType
from ..exceptions import ApiError

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_LOGGER = logging.getLogger(__name__)

# The server keeps an invocation stream open while the car works on the command;
# stop following it after this long.
FOLLOW_UP_TIMEOUT = 120.0

InvocationListener = Callable[[str, InvocationResponse], None]


class InvocationServiceClient:
    """Car command service — lock, unlock, climate, windows, pre-cleaning, honk/flash."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin
        self._listeners: list[InvocationListener] = []
        self._follow_ups: set[asyncio.Task[None]] = set()

    def add_listener(self, listener: InvocationListener) -> Callable[[], None]:
        """Call *listener(method, final_response)* once a command's stream has finished.

        Commands return as soon as the server accepts them; the final outcome
        (success, car offline, timeout, ...) arrives later and is reported here.
        Returns a function that removes the listener.
        """
        self._listeners.append(listener)

        def remove() -> None:
            with contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return remove

    async def cancel_follow_ups(self) -> None:
        """Stop following any in-flight command streams."""
        tasks = list(self._follow_ups)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def _svc(self) -> str:
        return self._connection.backend.invocation_svc

    def _request(self) -> InvocationRequest:
        return InvocationRequest(vin=self._vin)

    async def _call(self, method: str, request_bytes: bytes) -> bytes:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        stream = grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/{method}",
            request_bytes,
            metadata=metadata,
        )
        try:
            first = await anext(stream)
        except StopAsyncIteration:
            raise ApiError(f"{method} returned no invocation response") from None
        except BaseException:
            await stream.aclose()
            raise
        task = asyncio.create_task(self._follow_up(method, stream, first), name=f"polestar-invocation-{method}")
        self._follow_ups.add(task)
        task.add_done_callback(self._follow_ups.discard)
        return first

    @staticmethod
    def _parse_response(data: bytes) -> InvocationResponse | None:
        try:
            return InvocationEnvelope.from_bytes(data).response
        except Exception:  # noqa: BLE001
            return None

    async def _follow_up(self, method: str, stream, first: bytes) -> None:
        """Read the rest of a command's stream and report the final status to listeners."""
        last = self._parse_response(first)
        try:
            async with asyncio.timeout(FOLLOW_UP_TIMEOUT):
                async for message in stream:
                    parsed = self._parse_response(message)
                    if parsed is not None:
                        last = parsed
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Invocation stream for %s ended: %r", method, err)
        finally:
            with contextlib.suppress(Exception):
                await stream.aclose()
        if last is None:
            return
        for listener in list(self._listeners):
            try:
                listener(method, last)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Invocation listener failed for %s", method)

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
        """Start pre-cleaning and return the raw invocation response bytes."""
        req = PreCleaningRequest(request=self._request(), start=True)
        return await self._call("PreCleaning", req.to_bytes())

    async def precleaning_stop(self) -> bytes:
        """Stop pre-cleaning and return the raw invocation response bytes."""
        req = PreCleaningRequest(request=self._request(), start=False)
        return await self._call("PreCleaning", req.to_bytes())

    async def window_control(self, action: WindowControlType) -> ClimatizationResponse:
        req = WindowControlRequest(request=self._request(), windows_control=action)
        data = await self._call("WindowControl", req.to_bytes())
        return ClimatizationResponse.from_bytes(data)
