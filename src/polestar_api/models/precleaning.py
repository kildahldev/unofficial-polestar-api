"""Pre-cleaning status models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Timestamp


class PreCleaningRunningStatus(IntEnum):
    UNSPECIFIED = 0
    ON = 1
    OFF = 2
    PENDING = 3


class PreCleaningStartReason(IntEnum):
    UNSPECIFIED = 0
    REMOTE = 1
    MANUALLY_FROM_CAR = 2


class PreCleaningErrorType(IntEnum):
    UNSPECIFIED = 0
    GENERIC_ERROR = 1
    INTERRUPTED = 2


@dataclass(frozen=True)
class PreCleaningInfo(ProtoMessage, schema={
    1: "timestamp",
    4: "started_at",
    5: "ending_at",
    6: "running_status",
    7: "start_reason",
    8: "last_cycle_valid",
    9: "measured_air_quality_index",
    10: "measured_particulate_matter_2_5",
    11: "runtime_left_minutes",
    13: "error",
}):
    timestamp: Timestamp | None = None
    started_at: Timestamp | None = None
    ending_at: Timestamp | None = None
    running_status: PreCleaningRunningStatus = PreCleaningRunningStatus.UNSPECIFIED
    start_reason: PreCleaningStartReason = PreCleaningStartReason.UNSPECIFIED
    last_cycle_valid: bool = False
    measured_air_quality_index: int = 0
    measured_particulate_matter_2_5: int = 0
    runtime_left_minutes: int = 0
    error: PreCleaningErrorType = PreCleaningErrorType.UNSPECIFIED

    @property
    def is_running(self) -> bool:
        return self.running_status == PreCleaningRunningStatus.ON
