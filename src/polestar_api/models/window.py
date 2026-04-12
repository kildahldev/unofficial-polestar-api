"""Window control models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .invocation import InvocationRequest


class WindowControlType(IntEnum):
    UNSPECIFIED = 0
    OPEN_ALL = 1
    CLOSE_ALL = 2


@dataclass(frozen=True)
class WindowControlRequest(ProtoMessage, schema={1: "request", 2: "windows_control"}):
    request: InvocationRequest | None = None
    windows_control: WindowControlType = WindowControlType.UNSPECIFIED
