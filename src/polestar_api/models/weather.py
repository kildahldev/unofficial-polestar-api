"""Weather report at car's location."""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import ProtoMessage


@dataclass(frozen=True)
class WeatherReport(ProtoMessage, schema={
    1: "timestamp_epoch_millis",
    2: "temperature_celsius",
}):
    timestamp_epoch_millis: int = 0
    temperature_celsius: float = 0.0
