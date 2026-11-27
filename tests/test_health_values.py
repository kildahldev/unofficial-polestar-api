"""Enum values the backend sends that the models do or do not know."""

from polestar_api.codec import encode
from polestar_api.models.health import BrakeFluidLevelWarning, Health, ServiceWarning

SCHEMA = {
    "days": (3, "int32"),
    "service": (5, "int32"),
    "brake_fluid": (6, "int32"),
}


def test_overdue_and_critical_values():
    health = Health.from_bytes(encode(SCHEMA, {"service": 9, "brake_fluid": 3}))

    assert health.service_warning == ServiceWarning.REGULAR_MAINTENANCE_OVERDUE
    assert health.brake_fluid_level_warning == BrakeFluidLevelWarning.CRITICALLY_LOW


def test_unknown_value_does_not_break_the_message():
    health = Health.from_bytes(encode(SCHEMA, {"days": 10, "service": 99}))

    assert health.service_warning == ServiceWarning.UNSPECIFIED
    assert health.days_to_service == 10
