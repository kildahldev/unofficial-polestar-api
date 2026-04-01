"""Charging models — target SoC, amp limit, charge timer, charge now, stop/resume."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import ResponseStatus


# -- Target SoC --


class ChargeTargetLevelSettingType(IntEnum):
    UNSPECIFIED = 0
    DAILY = 1
    LONG_TRIP = 2
    CUSTOM = 3


@dataclass(frozen=True)
class SetTargetSocRequest(ProtoMessage, schema={
    1: "target_level",
    2: "setting_type",
}):
    target_level: int = 0
    setting_type: ChargeTargetLevelSettingType = ChargeTargetLevelSettingType.UNSPECIFIED


@dataclass(frozen=True)
class TargetSocResponse(ProtoMessage, schema={
    1: "response_status",
    2: "target_level",
}):
    response_status: ResponseStatus | None = None
    target_level: int = 0


# -- Amp Limit --


@dataclass(frozen=True)
class SetAmpLimitRequest(ProtoMessage, schema={1: "amperage_limit"}):
    amperage_limit: int = 0


@dataclass(frozen=True)
class AmpLimitResponse(ProtoMessage, schema={
    1: "response_status",
    2: "amperage_limit",
}):
    response_status: ResponseStatus | None = None
    amperage_limit: int = 0


# -- Charge Timer --


@dataclass(frozen=True)
class BatteryChargeTimer(ProtoMessage, schema={
    1: "start",
    2: "stop",
    3: "activated",
    4: "timezone_offset",
}):
    start: int = 0
    stop: int = 0
    activated: bool = False
    timezone_offset: int = 0


@dataclass(frozen=True)
class SetChargeTimerRequest(ProtoMessage, schema={1: "timer"}):
    timer: BatteryChargeTimer | None = None


@dataclass(frozen=True)
class ChargeTimerResponse(ProtoMessage, schema={
    1: "response_status",
    2: "timer",
}):
    response_status: ResponseStatus | None = None
    timer: BatteryChargeTimer | None = None


# -- Charge Now --


class ChargeNowOptions(IntEnum):
    UNSPECIFIED = 0
    CHARGE_NOW = 1
    OVERRIDE = 2
    NOT_APPLICABLE = 3


@dataclass(frozen=True)
class ChargeNowRequest(ProtoMessage, schema={1: "charge_now"}):
    charge_now: bool = False


@dataclass(frozen=True)
class ChargeNowResponse(ProtoMessage, schema={1: "response_status"}):
    response_status: ResponseStatus | None = None


# -- Stop / Resume Charging --


class StopResumeChargingCommand(IntEnum):
    UNSPECIFIED = 0
    STOP_CHARGING = 1
    RESUME_CHARGING = 2


@dataclass(frozen=True)
class StopResumeChargingRequest(ProtoMessage, schema={1: "command"}):
    command: StopResumeChargingCommand = StopResumeChargingCommand.UNSPECIFIED


@dataclass(frozen=True)
class StopResumeChargingResponse(ProtoMessage, schema={1: "response_status"}):
    response_status: ResponseStatus | None = None
