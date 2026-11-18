"""Regression test for ClimateServiceClient._parse_digital_twin's wire mapping.

Field 11/12 seat order was originally rear-right-then-rear-left; verified
wrong against a real car's per-seat heating state by
ericyew/unofficial-polestar-api, which found the wire order is actually
front-left, front-right, rear-left, rear-right (i.e. 11 -> rear_left,
12 -> rear_right).
"""

from __future__ import annotations

from polestar_api.codec import encode
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.services.climate import ClimateServiceClient


def _digital_twin_payload(**fields: int | float | bool) -> bytes:
    schema = {name: (num, "int64") for name, num in _FIELD_NUMBERS.items()}
    # Temperatures are doubles.
    schema["current_temperature_celsius"] = (7, "double")
    schema["target_temperature_celsius"] = (8, "double")
    return encode(schema, fields)


_FIELD_NUMBERS = {
    "running_status": 2,
    "time_remaining": 3,
    "front_left_seat": 9,
    "front_right_seat": 10,
    "rear_left_seat": 11,
    "rear_right_seat": 12,
    "steering_wheel": 13,
    "request_type": 15,
}


def test_seats_are_not_swapped():
    data = _digital_twin_payload(
        front_left_seat=2,  # LEVEL1
        front_right_seat=3,  # LEVEL2
        rear_left_seat=4,  # LEVEL3
        rear_right_seat=1,  # OFF
    )
    info = ClimateServiceClient._parse_digital_twin(data)

    assert info.front_left_seat == HeatingIntensity.LEVEL1
    assert info.front_right_seat == HeatingIntensity.LEVEL2
    assert info.rear_left_seat == HeatingIntensity.LEVEL3
    assert info.rear_right_seat == HeatingIntensity.OFF


def test_temperatures_are_decoded():
    data = _digital_twin_payload(current_temperature_celsius=21.5, target_temperature_celsius=22.0)
    info = ClimateServiceClient._parse_digital_twin(data)

    assert info.current_temperature_celsius == 21.5
    assert info.target_temperature_celsius == 22.0


def test_missing_optional_fields_are_none():
    data = _digital_twin_payload(time_remaining=5)
    info = ClimateServiceClient._parse_digital_twin(data)

    assert info.current_temperature_celsius is None
    assert info.front_left_seat is None
    assert info.started_at is None
    assert info.ending_at is None
