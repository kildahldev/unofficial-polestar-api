"""Minimal gRPC call helpers using grpclib."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from grpclib.client import Channel
from grpclib.const import Cardinality, Status
from grpclib.encoding.base import CodecBase
from grpclib.exceptions import GRPCError

_LOGGER = logging.getLogger(__name__)

# Transient gRPC statuses worth retrying (matches app's RetryPolicy).
_RETRIABLE_STATUSES = {Status.UNAVAILABLE, Status.INTERNAL}


class _RawCodec(CodecBase):
    """Pass-through codec for raw protobuf bytes (no generated stubs)."""

    __content_subtype__ = "proto"

    def encode(self, message, message_type):
        return message

    def decode(self, data: bytes, message_type):
        return data


_RAW_CODEC = _RawCodec()


async def unary_unary(
    channel: Channel,
    method: str,
    request_data: bytes,
    *,
    metadata: dict[str, str] | None = None,
) -> bytes:
    """Make a unary-unary gRPC call, returning raw response bytes."""
    async with channel.request(
        method,
        Cardinality.UNARY_UNARY,
        request_type=bytes,
        reply_type=bytes,
        metadata=metadata or {},
    ) as stream:
        await stream.send_message(request_data, end=True)
        return await stream.recv_message()


async def unary_stream(
    channel: Channel,
    method: str,
    request_data: bytes,
    *,
    metadata: dict[str, str] | None = None,
    retries: int = 2,
) -> AsyncIterator[bytes]:
    """Make a server-streaming gRPC call with retry on transient errors.

    Chronos streaming endpoints are subscriptions: the server sends one or
    more messages then keeps the stream open for live updates.  The server
    may also send GOAWAY/UNAVAILABLE before delivering any data; the Android
    app handles this via its RetryPolicy.  We retry only when no messages
    have been yielded yet.
    """
    last_exc: Exception | None = None
    for attempt in range(1 + retries):
        if attempt:
            delay = min(2 ** attempt, 8)
            _LOGGER.debug("Retry %d/%d for %s after %.1fs", attempt, retries, method, delay)
            await asyncio.sleep(delay)
        yielded = False
        try:
            async with channel.request(
                method,
                Cardinality.UNARY_STREAM,
                request_type=bytes,
                reply_type=bytes,
                metadata=metadata or {},
            ) as stream:
                await stream.send_message(request_data, end=True)
                async for message in stream:
                    yielded = True
                    yield message
            return  # stream closed normally
        except GRPCError as exc:
            if yielded:
                # Server closed the stream after delivering data — normal
                # for subscription-style RPCs (e.g. UNAVAILABLE after GOAWAY).
                return
            last_exc = exc
            if exc.status not in _RETRIABLE_STATUSES:
                raise
            _LOGGER.debug("Transient gRPC error on %s: %s", method, exc)
        except OSError as exc:
            if yielded:
                return
            last_exc = exc
            _LOGGER.debug("Connection error on %s: %s", method, exc)
    if last_exc is not None:
        raise last_exc
