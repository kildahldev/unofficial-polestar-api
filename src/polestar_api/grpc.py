"""Minimal gRPC call helpers using grpclib."""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator

from grpclib.client import Channel
from grpclib.const import Cardinality


def _frame(data: bytes) -> bytes:
    """Wrap protobuf bytes in gRPC length-prefixed frame."""
    return b"\x00" + struct.pack(">I", len(data)) + data


def _unframe(data: bytes) -> bytes:
    """Strip gRPC length-prefixed frame header."""
    # compressed_flag (1 byte) + length (4 bytes) + payload
    return data[5:]


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
        request_type=None,
        reply_type=None,
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
) -> AsyncIterator[bytes]:
    """Make a server-streaming gRPC call, yielding raw response bytes."""
    async with channel.request(
        method,
        Cardinality.UNARY_STREAM,
        request_type=None,
        reply_type=None,
        metadata=metadata or {},
    ) as stream:
        await stream.send_message(request_data, end=True)
        async for message in stream:
            yield message
