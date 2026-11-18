"""Climatization start/stop request and response models for invocation service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Annotated

from ..wire import Float32, ProtoMessage
from .invocation import InvocationRequest, InvocationResponse


class HeatingIntensity(IntEnum):
    UNSPECIFIED = 0
    OFF = 1
    LEVEL1 = 2
    LEVEL2 = 3
    LEVEL3 = 4


@dataclass(frozen=True)
class ClimatizationStartRequest(ProtoMessage, schema={
    1: "request",
    2: "start",
    3: "compartment_temperature_celsius",
    4: "front_right_seat",
    5: "front_left_seat",
    6: "rear_right_seat",
    7: "rear_left_seat",
    8: "steering_wheel",
}):
    request: InvocationRequest | None = None
    start: bool = True
    compartment_temperature_celsius: Annotated[float, Float32] = 0.0
    front_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    front_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    steering_wheel: HeatingIntensity = HeatingIntensity.UNSPECIFIED


@dataclass(frozen=True)
class ClimatizationStopRequest(ProtoMessage, schema={1: "request"}):
    request: InvocationRequest | None = None


@dataclass(frozen=True)
class ClimatizationResponse(ProtoMessage, schema={1: "response"}):
    response: InvocationResponse | None = None
