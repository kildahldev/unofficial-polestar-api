"""gRPC connection management with bearer token injection."""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING

from grpclib.client import Channel

if TYPE_CHECKING:
    from .auth import AuthManager


class GrpcConnection:
    """Manages a grpclib Channel with automatic bearer token injection."""

    def __init__(self, host: str, port: int, auth: AuthManager) -> None:
        self._host = host
        self._port = port
        self._auth = auth
        self._channel: Channel | None = None

    @property
    def channel(self) -> Channel:
        if self._channel is None:
            ssl_context = ssl.create_default_context()
            self._channel = Channel(
                host=self._host,
                port=self._port,
                ssl=ssl_context,
            )
        return self._channel

    async def get_metadata(self) -> dict[str, str]:
        """Return gRPC metadata with a valid bearer token."""
        token = await self._auth.ensure_valid_token()
        return {"authorization": f"Bearer {token}"}

    async def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
