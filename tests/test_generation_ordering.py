"""A command must not look like it was silently undone.

Tier polls, post-command refreshes and live streams all write the shared
snapshot concurrently, and they can finish in whatever order the network
decides. ``next_fetch_generation``/``_async_apply_values`` claim a sequence
number per fetch so a slow write started earlier can't land after a faster,
newer one and resurrect pre-command state.
"""

from __future__ import annotations

from .test_unsupported_entities import FakeRegistry, FakeVehicle, _coordinator, _load


def test_next_fetch_generation_increments(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _coordinator(module, FakeVehicle({}))

    assert coordinator.next_fetch_generation() == 1
    assert coordinator.next_fetch_generation() == 2


def test_apply_values_ignores_a_superseded_generation(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _coordinator(module, FakeVehicle({}))
    coordinator.data = None
    coordinator.async_update_listeners = lambda: None

    newer = coordinator.next_fetch_generation()
    older = coordinator.next_fetch_generation()
    # Deliberately applied out of order: `older` was claimed second, so the
    # higher number is actually the newer fetch.
    coordinator._async_apply_values({"battery": "fresh"}, older)
    assert coordinator.data.battery == "fresh"

    coordinator._async_apply_values({"battery": "stale"}, newer)
    assert coordinator.data.battery == "fresh", "a stale generation overwrote fresh state"


def test_apply_values_tracks_generations_per_attribute(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _coordinator(module, FakeVehicle({}))
    coordinator.data = None
    coordinator.async_update_listeners = lambda: None

    first = coordinator.next_fetch_generation()
    second = coordinator.next_fetch_generation()

    coordinator._async_apply_values({"climate": "on"}, second)
    coordinator._async_apply_values({"battery": "80%"}, first)

    assert coordinator.data.climate == "on"
    assert coordinator.data.battery == "80%"


def test_slow_poll_cannot_revert_a_newer_refresh(monkeypatch):
    """The real race: a fetch that claimed its generation first but finished last."""
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _coordinator(module, FakeVehicle({}))
    coordinator.data = None
    coordinator.async_update_listeners = lambda: None

    slow_generation = coordinator.next_fetch_generation()
    fast_generation = coordinator.next_fetch_generation()

    # The fast, post-command refresh finishes first.
    coordinator._async_apply_values({"climate": "on"}, fast_generation)
    assert coordinator.data.climate == "on"

    # The slow poll, which started earlier, finishes after it.
    coordinator._async_apply_values({"climate": "off"}, slow_generation)
    assert coordinator.data.climate == "on", "a slow poll reverted a newer result"


def test_unsupported_probe_is_claimed_on_first_poll_then_once_a_day(monkeypatch):
    """UNIMPLEMENTED endpoints are re-probed by elapsed time, not poll count."""
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _coordinator(module, FakeVehicle({}))

    clock = [1_000_000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    assert coordinator._claim_unsupported_probe() is True
    for _ in range(20):
        clock[0] += 300
        assert coordinator._claim_unsupported_probe() is False

    clock[0] += module._UNSUPPORTED_REPROBE_INTERVAL
    assert coordinator._claim_unsupported_probe() is True


def test_lock_error_is_a_failure_even_when_the_invocation_says_sent(monkeypatch):
    """CarLockResponse.lock_error is where 'a door is ajar' actually shows up."""
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _coordinator(module, FakeVehicle({}))

    from polestar_api.models.invocation import InvocationResponse, InvocationStatus
    from polestar_api.models.locks import CarLockResponse

    ok = CarLockResponse(response=InvocationResponse(status=InvocationStatus.SENT), lock_error=0)
    refused = CarLockResponse(response=InvocationResponse(status=InvocationStatus.SENT), lock_error=3)

    assert coordinator._command_succeeded(ok)
    assert not coordinator._command_succeeded(refused)
    assert "3" in coordinator._command_error_message(refused, "Lock command failed")
