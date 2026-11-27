"""Parking climatization status parsing."""

from polestar_api.codec import encode
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.services.climate import ClimateServiceClient


def test_seat_positions():
    schema = {
        "front_left": (9, "int32"),
        "front_right": (10, "int32"),
        "rear_left": (11, "int32"),
        "rear_right": (12, "int32"),
    }
    data = encode(schema, {"front_left": 2, "front_right": 3, "rear_left": 4, "rear_right": 1})

    info = ClimateServiceClient._parse_digital_twin(data)

    assert info.front_left_seat == HeatingIntensity.LEVEL1
    assert info.front_right_seat == HeatingIntensity.LEVEL2
    assert info.rear_left_seat == HeatingIntensity.LEVEL3
    assert info.rear_right_seat == HeatingIntensity.OFF
