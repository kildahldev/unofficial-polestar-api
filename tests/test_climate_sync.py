"""Polestar matches Volvo: climate action as a switch attribute, weather report time on outside temperature."""

import importlib.util
import re
import sys
import types
from datetime import UTC
from pathlib import Path

import pytest

from polestar_api.models.climate import ClimatizationInfo, ClimatizationRequestType, HeatOrCoolAction
from polestar_api.models.weather import WeatherReport

ROOT = Path(__file__).parents[1] / "custom_components" / "polestar"


@pytest.fixture
def utils(monkeypatch):
    ha = types.ModuleType("homeassistant")
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.UTC = UTC
    util.dt = dt
    ha.util = util
    for name, mod in (("homeassistant", ha), ("homeassistant.util", util), ("homeassistant.util.dt", dt)):
        monkeypatch.setitem(sys.modules, name, mod)
    spec = importlib.util.spec_from_file_location("polestar_utils_under_test", ROOT / "utils.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_action_words_match_volvo(utils):
    for src, want in [
        (HeatOrCoolAction.COOLING, "cooling"),
        (HeatOrCoolAction.COOLING_FAST, "cooling"),
        (HeatOrCoolAction.HEATING, "heating"),
        (HeatOrCoolAction.VENTILATION_ONLY, "ventilating"),
        (HeatOrCoolAction.NOT_REQUIRED, "not_required"),
        (HeatOrCoolAction.UNDEFINED, None),
    ]:
        assert utils.climate_action(ClimatizationInfo(heat_or_cool_action=src)) == want


def test_climate_attributes(utils):
    info = ClimatizationInfo(
        time_remaining=30,
        request_type=ClimatizationRequestType.NOW_FROM_REMOTE,
        heat_or_cool_action=HeatOrCoolAction.COOLING,
        target_temperature_celsius=22.0,
    )
    assert utils.climate_attributes(info) == {
        "runtime_left_minutes": 30,
        "start_reason": "now_from_remote",
        "action": "cooling",
        "target_temperature": 22.0,
    }
    assert utils.climate_attributes(None) == {}


def test_outside_temperature_reports_the_weather_time(utils):
    report = WeatherReport(timestamp_epoch_millis=1_700_000_000_000, temperature_celsius=21.6)
    assert utils.weather_attributes(report)["report_time"].startswith("2023-11-14")
    assert utils.weather_attributes(None) == {}


def test_sensor_wiring():
    src = (ROOT / "sensor.py").read_text()
    assert 'key="climate_heat_or_cool_action"' not in src
    assert src.count("suggested_unit_of_measurement=UnitOfPressure.PSI") == 4
    assert "attrs_fn=lambda d: weather_attributes(d.weather)" in src
    assert "attrs_fn=lambda d: climate_attributes(d.climate)" in (ROOT / "switch.py").read_text()


def test_charge_timer_switch_is_never_unknown_for_an_unset_timer(utils):
    from types import SimpleNamespace as NS

    assert utils.charge_timer_active(None) is None  # no answer yet
    assert utils.charge_timer_active(NS(timer=None)) is False  # answered, no timer set
    assert utils.charge_timer_active(NS(timer=NS(activated=False))) is False
    assert utils.charge_timer_active(NS(timer=NS(activated=True))) is True
    assert "is_on_fn=lambda d: charge_timer_active(d.charge_timer)" in (ROOT / "switch.py").read_text()


def test_entry_title_matches_volvo_style(utils):
    assert utils.entry_title("Polestar 2", 2026, "YSMVSFDR8TL421810") == "Polestar 2 2026"
    assert utils.entry_title("Polestar 2", None, "YSMVSFDR8TL421810") == "Polestar 2 YSMVSFDR8TL421810"
    assert utils.entry_title(None, None, "V1") == "Polestar V1"
    src = (ROOT / "config_flow.py").read_text()
    assert "title=self._titles.get(vin) or entry_title(None, None, vin)" in src


def test_flatten_attributes_one_row_per_field(utils):
    flat = utils.flatten_attributes(
        {
            "app": {"slug": "polestar-2", "structure_week": "202611", "internet_activation": None},
            "order": {"engine": "Long range", "features": ["A", "B"], "specifications": {"Battery": "82 kWh"}},
            "c3": {"supportsHonkFlash": True, "propulsion": {"engine_type": "electric"}},
            "empty": {},
        }
    )
    assert flat == {
        "app_slug": "polestar-2",
        "app_structure_week": "202611",
        "order_engine": "Long range",
        "order_features": "A, B",
        "order_specifications_battery": "82 kWh",
        "c3_supports_honk_flash": True,
        "c3_propulsion_engine_type": "electric",
    }
    assert utils.flatten_attributes(None) == {}
    src = (ROOT / "sensor.py").read_text()
    assert "_unrecorded_attributes = frozenset({MATCH_ALL})" in src and "**flatten_attributes(" in src


def test_in_use_is_driving_only_and_fluids_are_problem_flags(utils):
    from polestar_api.models.availability import UsageMode
    from polestar_api.models.health import BrakeFluidLevelWarning, WasherFluidLevelWarning

    assert utils.driving(UsageMode.DRIVING) is True
    for mode in (UsageMode.INACTIVE, UsageMode.ABANDONED, UsageMode.ACTIVE, UsageMode.CONVENIENCE):
        assert utils.driving(mode) is False
    assert utils.driving(UsageMode.UNSPECIFIED) is None
    assert utils.level_problem(BrakeFluidLevelWarning.NO_WARNING) is False
    assert utils.level_problem(BrakeFluidLevelWarning.TOO_LOW) is True
    assert utils.level_problem(BrakeFluidLevelWarning.CRITICALLY_LOW) is True
    assert utils.level_problem(WasherFluidLevelWarning.UNSPECIFIED) is None


def test_light_status_lists_every_light(utils):
    from polestar_api.models.health import ExteriorLightWarning, Health

    health = Health(
        turn_indication_front_left_warning=ExteriorLightWarning.NO_WARNING,
        low_beam_right_warning=ExteriorLightWarning.FAILURE,
        registration_plate_light_warning=ExteriorLightWarning.NO_WARNING,
        brake_light_center_warning=ExteriorLightWarning.UNSPECIFIED,
    )
    attrs = utils.light_attributes(health)
    assert attrs["front_left_turn_indicator"] == "ok"
    assert attrs["right_low_beam"] == "failure"
    assert attrs["registration_plate_light"] == "ok"
    assert attrs["center_brake_light"] == "unknown"
    assert health.any_light_failure is True


def test_old_warning_entities_are_gone_and_removed_from_the_registry():
    sensor_src = (ROOT / "sensor.py").read_text()
    binary_src = (ROOT / "binary_sensor.py").read_text()
    for key in ("service_warning", "brake_fluid_warning", "washer_fluid_warning", "low_voltage_battery_warning"):
        assert f'key="{key}"' not in sensor_src
    assert 'key="is_locked"' not in binary_src
    assert 'key="in_use"' in binary_src and 'translation_key="light_failure"' in binary_src
    init_src = (ROOT / "__init__.py").read_text()
    assert "_async_remove_replaced_entities(hass, vehicle.vin)" in init_src


def test_software_stream_returns_at_once_on_an_empty_first_message():
    from pathlib import Path

    source = Path("src/polestar_api/services/ota.py").read_text()
    after_info = source.split('return CarSoftwareInfo.from_bytes(raw["info"])', 1)[1]
    assert after_info.lstrip().startswith("# An empty first message")
    assert "return None" in after_info.split("except", 1)[0]


def test_installed_software_version_comes_from_the_car_record():
    from pathlib import Path

    assert "self.installed_software_version = car.consumer_software_version or None" in Path(
        "src/polestar_api/vehicle.py"
    ).read_text()
    coordinator = Path("custom_components/polestar/coordinator.py").read_text()
    assert 'getattr(vehicle, "installed_software_version", None)' in coordinator


def test_polestar_has_no_sunroof_sensor_and_an_old_one_is_removed():
    binary_src = (ROOT / "binary_sensor.py").read_text()
    assert 'key="sunroof"' not in binary_src
    assert '"sunroof",' in (ROOT / "__init__.py").read_text().split("_REPLACED_ENTITY_SUFFIXES", 1)[1].split(")", 1)[0]


def test_there_is_one_air_purification_switch_and_the_old_precleaning_one_is_removed():
    switch_src = (ROOT / "switch.py").read_text()
    assert 'key="precleaning"' not in switch_src
    assert 'key="air_purification"' in switch_src
    assert "entity_registry_enabled_default=False" not in switch_src.split('key="air_purification"', 1)[1].split("PolestarSwitchDescription(", 1)[0]
    init_src = (ROOT / "__init__.py").read_text()
    assert '"precleaning",' in init_src.split("_REPLACED_ENTITY_SUFFIXES", 1)[1].split(")", 1)[0]
    assert '"switch"' in init_src.split("def _async_remove_replaced_entities", 1)[1]


def test_alarm_triggered_sensor(utils):
    from polestar_api.models.exterior import AlarmStatus, DoorsStatus, DoorStatus, ExteriorStatus

    assert utils.alarm_triggered(None) is None
    assert utils.alarm_triggered(ExteriorStatus()) is False  # nothing reported means no alarm
    idle = DoorsStatus(front_left=DoorStatus(alarm_status=AlarmStatus.OFF))
    assert utils.alarm_triggered(ExteriorStatus(doors=idle)) is False
    fired = DoorsStatus(
        front_left=DoorStatus(alarm_status=AlarmStatus.OFF), rear_right=DoorStatus(alarm_status=AlarmStatus.TRIGGERED)
    )
    assert utils.alarm_triggered(ExteriorStatus(doors=fired)) is True


def _data(available, reason="UNSPECIFIED", seconds=1_794_990_000):
    from types import SimpleNamespace as NS

    return NS(
        availability=NS(is_available=available, unavailable_reason=NS(name=reason), timestamp=NS(seconds=seconds)),
        battery=NS(timestamp=NS(seconds=seconds - 500)),
        odometer=None, health=None, precleaning=None, connectivity=None,
    )


def test_last_seen_is_the_newest_car_timestamp(utils):
    seen = utils.last_seen(_data(True, seconds=1_794_990_000))
    assert int(seen.timestamp()) == 1_794_990_000
    from types import SimpleNamespace as NS

    assert utils.last_seen(NS(availability=None, battery=None, odometer=None, health=None, precleaning=None, connectivity=None)) is None


def test_connection_text(utils):
    assert utils.connection_text(_data(True)) == "Online"
    # Short, and no clock time in the state, or every update would be a new history entry.
    assert utils.connection_text(_data(False, "NO_INTERNET")) == "Offline: no internet"
    assert utils.connection_text(_data(False, "CAR_IN_USE")) == "Offline: car in use"
    assert utils.connection_text(type("D", (), {"availability": None})()) == "Unknown"
    assert utils.connection_attributes(_data(True)) == {"detail": "The car can receive commands."}
    detail = utils.connection_attributes(_data(False, "CAR_IN_USE"))["detail"]
    assert detail.startswith("The car is in use. Commands may not reach")


def test_commands_are_only_refused_when_they_cannot_reach_the_car(utils):
    fmt = lambda moment: "19:32"  # noqa: E731
    assert utils.command_blocker(_data(True), fmt) is None
    assert utils.command_blocker(_data(False, "POWER_SAVING_MODE"), fmt) is None  # the car wakes for a command
    assert utils.command_blocker(_data(False, "UNSPECIFIED"), fmt) is None  # no reason: let it through
    assert utils.command_blocker(type("D", (), {"availability": None})(), fmt) is None
    blocked = utils.command_blocker(_data(False, "NO_INTERNET"), fmt)
    assert "offline since 19:32" in blocked and "Nothing was sent" in blocked
    assert "in use" in utils.command_blocker(_data(False, "CAR_IN_USE"), fmt)
    assert utils.command_blocker(_data(False, "OTA_INSTALLATION_IN_PROGRESS"), fmt)


def test_in_use_follows_driving_or_the_car_in_use_reason(utils):
    from types import SimpleNamespace as NS

    def avail(available, reason, mode):
        return NS(is_available=available, unavailable_reason=NS(name=reason), usage_mode=mode)

    from polestar_api.models.availability import UsageMode

    assert utils.in_use(None) is None
    assert utils.in_use(avail(True, "UNSPECIFIED", UsageMode.DRIVING)) is True
    assert utils.in_use(avail(False, "CAR_IN_USE", UsageMode.ACTIVE)) is True  # what the app shows as "In use"
    assert utils.in_use(avail(True, "CAR_IN_USE", UsageMode.INACTIVE)) is False  # a stale reason on an available car
    assert utils.in_use(avail(False, "NO_INTERNET", UsageMode.INACTIVE)) is False


def test_flatten_attributes_makes_raw_bytes_json_safe(utils):
    import json

    flat = utils.flatten_attributes({"reportsLightWarnings": b"\x01\x02\x15"})
    assert flat == {"reports_light_warnings": "1, 2, 21"}
    json.dumps(flat)


def test_switch_attributes_carry_what_the_removed_sensors_showed(utils):
    from types import SimpleNamespace

    climate = SimpleNamespace(
        time_remaining=10,
        request_type=None,
        heat_or_cool_action=None,
        target_temperature_celsius=22.0,
        current_temperature_celsius=18.5,
        is_active=True,
        ending_at=1_800_000_000,
    )
    attrs = utils.climate_attributes(climate)
    assert attrs["current_temperature"] == 18.5
    assert attrs["ends_at"].startswith("2027-01-15")

    idle = SimpleNamespace(**{**climate.__dict__, "is_active": False})
    assert "ends_at" not in utils.climate_attributes(idle)

    pre = SimpleNamespace(runtime_left_minutes=7, start_reason=None, error=None)
    assert utils.precleaning_attributes(pre)["runtime_left_minutes"] == 7
    assert "error" not in utils.precleaning_attributes(pre)
    assert utils.precleaning_attributes(None) == {}


def test_service_attributes_grade_the_warning(utils):
    from polestar_api.models.health import ServiceWarning

    assert utils.service_attributes(ServiceWarning.NO_WARNING) == {}
    assert utils.service_attributes(ServiceWarning.UNSPECIFIED) == {}
    assert utils.service_attributes(ServiceWarning.UNKNOWN_WARNING) == {}
    assert utils.service_attributes(ServiceWarning.REGULAR_MAINTENANCE_ALMOST_TIME) == {
        "service_urgency": "almost_due",
        "service_reason": "regular",
    }
    assert utils.service_attributes(ServiceWarning.ENGINE_HOURS_TIME) == {
        "service_urgency": "due",
        "service_reason": "engine_hours",
    }
    assert utils.service_attributes(ServiceWarning.DISTANCE_DRIVEN_OVERDUE) == {
        "service_urgency": "overdue",
        "service_reason": "distance",
    }


def test_tyre_attributes_only_when_pressures_are_reported(utils):
    from polestar_api.models.health import Health, TyrePressureWarning

    no_pressure = Health(front_left_tyre_pressure_warning=TyrePressureWarning.LOW_PRESSURE)
    assert utils.tyre_attributes(no_pressure) == {}
    assert utils.tyre_attributes(None) == {}
    health = Health(
        front_left_tyre_pressure_kpa=250.0,
        front_left_tyre_pressure_warning=TyrePressureWarning.NO_WARNING,
        front_right_tyre_pressure_warning=TyrePressureWarning.VERY_LOW_PRESSURE,
        rear_left_tyre_pressure_warning=TyrePressureWarning.HIGH_PRESSURE,
    )
    assert utils.tyre_attributes(health) == {
        "front_left_warning": "ok",
        "front_right_warning": "very_low",
        "rear_left_warning": "high",
    }
