"""Powertrain, battery capacity and capability flags decoded from the C3 car-information reply."""

import struct

from polestar_api.models.car_information import CarDetails, DigitalKeyType, DrivetrainType, EngineType


def _varint(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _field(num: int, wire: int, payload: bytes) -> bytes:
    return _varint(num << 3 | wire) + payload


def _ld(num: int, data: bytes) -> bytes:
    return _field(num, 2, _varint(len(data)) + data)


def test_propulsion_digital_key_and_flags_decode():
    propulsion = _field(1, 0, _varint(1)) + _field(5, 5, struct.pack("<f", 82.0)) + _field(6, 0, _varint(1))
    car = (
        _ld(1, b"VIN")
        + _ld(39, _field(1, 0, _varint(3)))
        + _ld(40, propulsion)
        + _field(43, 0, _varint(4))
        + _field(70, 0, _varint(1))
    )
    decoded = CarDetails.from_bytes(car)
    assert decoded.propulsion.engine_type is EngineType.ELECTRIC
    assert decoded.propulsion.drivetrain_type is DrivetrainType.AWD
    assert decoded.propulsion.battery_capacity_kwh == 82.0
    assert decoded.propulsion.fuel_tank_volume == 0
    assert decoded.digital_key.type is DigitalKeyType.POLESTAR_2
    assert decoded.num_doors == 4
    assert decoded.has_performance_software_upgrade is True
    assert decoded.supports_engine_start is False
