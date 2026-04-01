"""Parking climatization timer models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage


class TimerState(IntEnum):
    OFF = 0
    ON = 1
    NOT_SET = 2


class YesNo(IntEnum):
    NO = 0
    YES = 1


class DayStatus(IntEnum):
    NO = 0
    YES = 1
    DONE = 2


@dataclass(frozen=True)
class ClimateTimerObject(ProtoMessage, schema={
    1: "timer_state",
    2: "completion_time",
    3: "repeat_timer",
    4: "day_0",
    5: "day_1",
    6: "day_2",
    7: "day_3",
    8: "day_4",
    9: "day_5",
    10: "day_6",
}):
    timer_state: TimerState = TimerState.OFF
    completion_time: int = 0
    repeat_timer: YesNo = YesNo.NO
    day_0: DayStatus = DayStatus.NO
    day_1: DayStatus = DayStatus.NO
    day_2: DayStatus = DayStatus.NO
    day_3: DayStatus = DayStatus.NO
    day_4: DayStatus = DayStatus.NO
    day_5: DayStatus = DayStatus.NO
    day_6: DayStatus = DayStatus.NO
