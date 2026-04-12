"""gRPC connection management with bearer token injection."""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING

import grpclib.metadata
from grpclib.client import Channel
from grpclib.config import Configuration

from .backend import BackendProfile
from .grpc import _RAW_CODEC

if TYPE_CHECKING:
    from .auth import AuthManager

# The C3 server rejects non-Java gRPC user agents with UNIMPLEMENTED.
grpclib.metadata.USER_AGENT = "grpc-java-okhttp/1.68.2"

# Create SSL context at import time to avoid blocking the event loop.
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.set_alpn_protocols(["h2"])

# Match the Android app's OkHttp channel: keepAlive=30s, timeout=20s.
_GRPC_CONFIG = Configuration(
    _keepalive_time=30,
    _keepalive_timeout=20,
    _keepalive_permit_without_calls=False,
)


class GrpcConnection:
    """Manages a grpclib Channel with automatic bearer token injection."""

    def __init__(self, host: str, port: int, auth: AuthManager, backend: BackendProfile | None = None) -> None:
        self._host = host
        self._port = port
        self._auth = auth
        self.backend = backend or BackendProfile()
        self._channel: Channel | None = None

    @property
    def channel(self) -> Channel:
        if self._channel is None:
            self._channel = Channel(
                host=self._host,
                port=self._port,
                ssl=_SSL_CONTEXT,
                codec=_RAW_CODEC,
                config=_GRPC_CONFIG,
            )
        return self._channel

    async def get_metadata(self, vin: str | None = None) -> dict[str, str]:
        """Return gRPC metadata with a valid bearer token and optional VIN."""
        token = await self._auth.ensure_valid_token()
        metadata = {"authorization": f"Bearer {token}"}
        if vin:
            metadata["vin"] = vin
        return metadata

    async def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
