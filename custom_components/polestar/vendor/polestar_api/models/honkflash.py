"""Honk and flash models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .invocation import InvocationRequest, InvocationResponse


class HonkFlashAction(IntEnum):
    HONK_AND_FLASH = 0
    HONK = 1
    FLASH = 2


@dataclass(frozen=True)
class HonkAndFlashRequest(ProtoMessage, schema={1: "request", 2: "honk_flash_type"}):
    request: InvocationRequest | None = None
    honk_flash_type: HonkFlashAction = HonkFlashAction.HONK_AND_FLASH


@dataclass(frozen=True)
class HonkAndFlashResponse(ProtoMessage, schema={1: "response"}):
    response: InvocationResponse | None = None
