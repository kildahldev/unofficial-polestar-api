"""Climatization start/stop request and response models for invocation service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import ResponseStatus


class HeatingIntensity(IntEnum):
    UNSPECIFIED = 0
    OFF = 1
    LEVEL1 = 2
    LEVEL2 = 3
    LEVEL3 = 4


@dataclass(frozen=True)
class ClimatizationStartRequest(ProtoMessage, schema={
    2: "start",
    3: "compartment_temperature_celsius",
    4: "front_right_seat",
    5: "front_left_seat",
    6: "rear_right_seat",
    7: "rear_left_seat",
    8: "steering_wheel",
}):
    start: bool = True
    compartment_temperature_celsius: float = 0.0
    front_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    front_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    steering_wheel: HeatingIntensity = HeatingIntensity.UNSPECIFIED


class InvocationStatus(IntEnum):
    UNSPECIFIED = 0
    SUCCESS = 1
    FAILURE = 2
    TIMEOUT = 3


@dataclass(frozen=True)
class InvocationResponse(ProtoMessage, schema={
    1: "id",
    2: "vin",
    3: "status",
    4: "message",
    5: "timestamp",
}):
    id: str = ""
    vin: str = ""
    status: InvocationStatus = InvocationStatus.UNSPECIFIED
    message: str = ""
    timestamp: int = 0


@dataclass(frozen=True)
class ClimatizationResponse(ProtoMessage, schema={1: "response"}):
    response: InvocationResponse | None = None
