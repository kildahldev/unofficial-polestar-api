"""The boot (tailgate) lock state is read from the car's exterior data."""

from __future__ import annotations

from polestar_api.codec import encode
from polestar_api.models.exterior import LockStatus, OpenStatus
from polestar_api.services.exterior import ExteriorServiceClient


def _exterior(**fields: int) -> bytes:
    schema = {name: (number, "int32") for name, number in (("central_lock", 2), ("tailgate", 12), ("tailgate_lock", 16))}
    return encode(schema, fields)


def _parse(exterior: bytes):
    return ExteriorServiceClient._parse({"exterior": exterior})


def test_unlocked_boot_is_reported():
    status = _parse(_exterior(central_lock=2, tailgate=2, tailgate_lock=1))

    assert status.tailgate.status.lock_status == LockStatus.UNLOCKED
    assert status.tailgate.status.open_status == OpenStatus.CLOSED
    assert status.is_locked is True


def test_locked_boot_is_reported():
    status = _parse(_exterior(central_lock=2, tailgate=2, tailgate_lock=2))

    assert status.tailgate.status.lock_status == LockStatus.LOCKED


def test_a_partial_update_with_only_the_boot_lock_keeps_the_rest():
    full = _parse(_exterior(central_lock=2, tailgate=2, tailgate_lock=2))
    update = _parse(_exterior(tailgate_lock=1))

    merged = update.merge(full)

    assert merged.tailgate.status.lock_status == LockStatus.UNLOCKED
    assert merged.tailgate.status.open_status == OpenStatus.CLOSED
    assert merged.is_locked is True
