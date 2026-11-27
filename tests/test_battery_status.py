"""Cold battery status and the battery thermal event flag (from ericyew 5ebf781)."""

from __future__ import annotations

from polestar_api.codec import encode
from polestar_api.models.battery import Battery, ColdBatteryStatus
from polestar_api.models.health import Health


def test_cold_battery_status_is_read():
    data = encode({"cold": (30, "int32")}, {"cold": 5})

    assert Battery.from_bytes(data).cold_battery_status == ColdBatteryStatus.COLD_AND_LOW_SOC


def test_cold_battery_status_defaults_to_unspecified():
    data = encode({"level": (9, "int32")}, {"level": 1})

    assert Battery.from_bytes(data).cold_battery_status == ColdBatteryStatus.UNSPECIFIED


def test_an_unknown_cold_battery_status_does_not_break_the_battery_data():
    data = encode({"cold": (30, "int32"), "target": (9, "int32")}, {"cold": 99, "target": 12})

    battery = Battery.from_bytes(data)

    assert battery.cold_battery_status == ColdBatteryStatus.UNSPECIFIED
    assert battery.time_to_target == 12


def test_battery_thermal_event_is_read():
    data = encode({"event": (48, "bool")}, {"event": True})

    assert Health.from_bytes(data).battery_thermal_event_triggered


def test_no_thermal_event_when_the_car_does_not_send_one():
    data = encode({"days": (3, "int32")}, {"days": 10})

    assert not Health.from_bytes(data).battery_thermal_event_triggered
