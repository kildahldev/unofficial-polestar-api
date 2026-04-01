"""Climate / parking climatization models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from ..wire import ProtoMessage


class ClimatizationRunningStatus(IntEnum):
    UNDEFINED = 0
    IDLE = 1
    START_ATTEMPT = 2
    START_AFTER_DELAY = 3
    EXTERNAL_POWER_ONLY = 4
    ACTIVE = 5
    ACTIVE_WITH_PRECLEANING = 6
    PRECLEANING_ONLY = 7
    HEATER_ACTIVE = 8
    DELETE_TIMER = 9


class ClimatizationRequestType(IntEnum):
    UNDEFINED = 0
    NO_REQUEST = 1
    TIMER = 2
    NOW_FROM_HMI = 3
    NOW_FROM_REMOTE = 4
    PRECLEANING_FROM_HMI = 5
    PRECLEANING_FROM_REMOTE = 6
    HEATER_FROM_HMI = 7


class HeatOrCoolAction(IntEnum):
    UNDEFINED = 0
    NOT_REQUIRED = 1
    HEATING = 2
    COOLING = 3
    COOLING_FAST = 4
    VENTILATION_ONLY = 5


@dataclass(frozen=True)
class ClimatizationInfo(ProtoMessage, schema={
    1: "running_status",
    2: "request_type",
    3: "time_remaining",
    4: "heat_or_cool_action",
}):
    running_status: ClimatizationRunningStatus = ClimatizationRunningStatus.UNDEFINED
    request_type: ClimatizationRequestType = ClimatizationRequestType.UNDEFINED
    time_remaining: int = 0
    heat_or_cool_action: HeatOrCoolAction = HeatOrCoolAction.UNDEFINED

    @property
    def is_active(self) -> bool:
        return self.running_status in (
            ClimatizationRunningStatus.ACTIVE,
            ClimatizationRunningStatus.ACTIVE_WITH_PRECLEANING,
            ClimatizationRunningStatus.EXTERNAL_POWER_ONLY,
            ClimatizationRunningStatus.HEATER_ACTIVE,
        )
