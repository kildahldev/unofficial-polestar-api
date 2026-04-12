"""Battery and charging status models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Timestamp

class ChargerConnectionStatus(IntEnum):
    """C3 Battery.ChargerConnectionStatus."""
    UNSPECIFIED = 0
    CONNECTED = 1
    DISCONNECTED = 2
    FAULT = 3


class ChargingStatus(IntEnum):
    """C3 Battery.ChargingStatus."""
    UNSPECIFIED = 0
    CHARGING = 1
    IDLE = 2
    SCHEDULED = 3
    DISCHARGING = 4
    ERROR = 5
    SMART_CHARGING = 6
    DONE = 7
    SMART_CHARGING_PAUSED = 8


class ChargingType(IntEnum):
    """C3 Battery.ChargingType."""
    UNSPECIFIED = 0
    NONE = 1
    AC = 2
    DC = 3
    WIRELESS = 4


class ChargerPowerStatus(IntEnum):
    UNSPECIFIED = 0
    NO_POWER = 1
    INITIALIZING = 2
    AVAILABLE_BUT_INACTIVE = 3
    PROVIDING_POWER = 4
    FAULT = 5


@dataclass(frozen=True)
class Battery(ProtoMessage, schema={
    1: "timestamp",
    2: "charge_level",
    3: "avg_consumption",
    4: "range_km",
    5: "time_to_full",
    6: "charger_connection_status",
    7: "charging_status",
    8: "range_miles",
    9: "time_to_target",
    10: "power_watts",
    11: "current_amps",
    12: "avg_consumption_auto",
    13: "avg_consumption_since_charge",
    14: "total_consumption_wh",
    15: "total_consumption_wh_auto",
    16: "total_consumption_wh_since_charge",
    17: "charging_type",
    18: "voltage_volts",
    19: "time_to_min_soc",
    20: "consumption_wh_manual",
    21: "consumption_wh_auto",
    22: "consumption_wh_since_charge",
    23: "consumption_pct_manual",
    24: "consumption_pct_auto",
    25: "consumption_pct_since_charge",
    26: "charger_power_status",
}):
    timestamp: Timestamp | None = None
    charge_level: float = 0.0
    avg_consumption: float = 0.0
    range_km: float = 0.0
    time_to_full: int = 0
    charger_connection_status: ChargerConnectionStatus = ChargerConnectionStatus.UNSPECIFIED
    charging_status: ChargingStatus = ChargingStatus.UNSPECIFIED
    range_miles: float = 0.0
    time_to_target: int = 0
    power_watts: int = 0
    current_amps: int = 0
    avg_consumption_auto: float = 0.0
    avg_consumption_since_charge: float = 0.0
    total_consumption_wh: float = 0.0
    total_consumption_wh_auto: float = 0.0
    total_consumption_wh_since_charge: float = 0.0
    charging_type: ChargingType = ChargingType.UNSPECIFIED
    voltage_volts: int = 0
    time_to_min_soc: int = 0
    consumption_wh_manual: float = 0.0
    consumption_wh_auto: float = 0.0
    consumption_wh_since_charge: float = 0.0
    consumption_pct_manual: float = 0.0
    consumption_pct_auto: float = 0.0
    consumption_pct_since_charge: float = 0.0
    charger_power_status: ChargerPowerStatus = ChargerPowerStatus.UNSPECIFIED

    @property
    def is_charging(self) -> bool:
        return self.charging_status == ChargingStatus.CHARGING

    @property
    def is_plugged_in(self) -> bool:
        return self.charger_connection_status == ChargerConnectionStatus.CONNECTED



@dataclass(frozen=True)
class GetBatteryResponse(ProtoMessage, schema={1: "id", 2: "vin", 3: "battery"}):
    id: str = ""
    vin: str = ""
    battery: Battery | None = None
