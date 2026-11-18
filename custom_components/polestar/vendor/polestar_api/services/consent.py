"""Data-sharing / privacy-consent service (``userServices.PrivacySettings``).

See ``models.consent`` for notes on which calls were directly observed in
the decompiled app versus schema-derived best-effort.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.consent import (
    PrivacySetting,
    PrivacySettingDetail,
    PrivacySettingStateExRequest,
    PrivacySettingsStreamRequest,
    RemoteFunctionDataSharing,
    RemoteFunctionDataSharingRequest,
    SetPrivacySettingStateRequest,
)

if TYPE_CHECKING:
    from ..connection import GrpcConnection


class ConsentServiceClient:
    """Data-sharing / privacy-consent settings for a car."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.privacy_settings_svc

    async def _metadata(self) -> dict[str, str]:
        return await self._connection.get_metadata(self._vin)

    async def get_remote_function_data_sharing(self) -> RemoteFunctionDataSharing | None:
        """Read the overall "share remote function data" toggle."""
        request = RemoteFunctionDataSharingRequest(vin=self._vin)
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetRemoteFunctionDataSharing",
            request.to_bytes(),
            metadata=metadata,
        )
        if not data:
            return None
        return RemoteFunctionDataSharing.from_bytes(data)

    async def stream_privacy_settings(self) -> AsyncIterator[PrivacySetting]:
        """Subscribe to the per-category privacy/data-sharing settings.

        This is a genuine subscription RPC (``...V2Stream``) — it may stay
        open and keep yielding updates rather than closing after an initial
        batch. Callers that just want a one-shot snapshot should stop
        iterating once satisfied rather than waiting for the stream to end.
        """
        request = PrivacySettingsStreamRequest(vin=self._vin)
        metadata = await self._metadata()
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetPrivacySettingsV2Stream",
            request.to_bytes(),
            metadata=metadata,
        ):
            yield PrivacySetting.from_bytes(data)

    async def get_privacy_setting(self, service_id: str, locale: str = "en") -> PrivacySettingDetail | None:
        """A single named privacy setting's current state, with display text."""
        request = PrivacySettingStateExRequest(vin=self._vin, service_id=service_id, locale=locale)
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetPrivacySettingStateEx",
            request.to_bytes(),
            metadata=metadata,
        )
        if not data:
            return None
        return PrivacySettingDetail.from_bytes(data)

    async def set_privacy_setting(self, service_id: str, enabled: bool) -> None:
        """Set a single named privacy setting's enabled state.

        Best-effort: see the module docstring in ``models.consent``. The
        RPC method name/path is inferred by convention from the sibling
        ``Get*`` calls on this service, not directly observed.
        """
        request = SetPrivacySettingStateRequest(vin=self._vin, service_id=service_id, enabled=enabled)
        metadata = await self._metadata()
        await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/SetPrivacySettingState",
            request.to_bytes(),
            metadata=metadata,
        )
