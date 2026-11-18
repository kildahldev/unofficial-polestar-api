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
