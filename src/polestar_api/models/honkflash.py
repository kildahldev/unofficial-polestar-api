"""Honk and flash models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import ResponseStatus


class HonkFlashAction(IntEnum):
    UNDEFINED = 0
    HONK = 1
    FLASH = 2
    HONK_AND_FLASH = 3


@dataclass(frozen=True)
class HonkAndFlashRequest(ProtoMessage, schema={1: "action"}):
    action: HonkFlashAction = HonkFlashAction.UNDEFINED


@dataclass(frozen=True)
class HonkAndFlashResponse(ProtoMessage, schema={1: "response_status"}):
    response_status: ResponseStatus | None = None
