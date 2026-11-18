"""DataUpdateCoordinator for Polestar vehicles."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import MISSING, dataclass, field, fields, replace
from datetime import time as dt_time, timedelta
from typing import TYPE_CHECKING, Any

from grpclib.const import Status as GrpcStatus
from grpclib.exceptions import GRPCError
from homeassistant.components import persistent_notification
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from polestar_api.exceptions import AuthError, TokenExpiredError, is_unsupported_feature_error
from polestar_api.models.availability import Availability
from polestar_api.models.battery import Battery
from polestar_api.models.charge_location import ChargeLocation
from polestar_api.models.charging import (
    AmpLimitResponse,
    BatteryChargeTimer,
    ChargeTargetLevelSettingType,
    ChargeTimerResponse,
    DailyTime,
    TimeZoneOffset,
    TargetSocResponse,
)
from polestar_api.models.climate import ClimatizationInfo
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.models.common import Location, ResponseStatusCode
from polestar_api.models.consent import RemoteFunctionDataSharing
from polestar_api.models.connectivity import ConnectivityInfo
from polestar_api.models.dashboard import DashboardStatus
from polestar_api.models.exterior import ExteriorStatus
from polestar_api.models.health import Health
from polestar_api.models.invocation import InvocationStatus
from polestar_api.models.odometer import OdometerStatus
from polestar_api.models.ota import CarSoftwareInfo, Scheduler, SoftwareState
from polestar_api.models.parking_climate_timer import (
    ParkingClimateTimer,
    ParkingClimateTimerSettings,
)
from polestar_api.models.precleaning import PreCleaningInfo
from polestar_api.models.weather import WeatherReport

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    STREAM_MAX_RETRIES,
    STREAM_MIN_RESUBSCRIBE_INTERVAL,
    STREAM_RETRY_DELAY,
)
from .utils import local_utc_offset_minutes

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from polestar_api.vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)
# Measured against a real car: the cloud reflects a lock/unlock roughly 3-30s
# after the command is accepted, and a climatisation start can take well over a
# minute. A schedule that stops too early makes the entity fall back to the
# pre-command snapshot before the car has reported anything, which reads as
# the command having been silently undone.
_POST_COMMAND_REFRESH_DELAYS: tuple[int, ...] = (3, 5, 10, 15, 30, 60)
# When a running stream already covers the attribute it reports the change
# within seconds on its own, so the refreshes are only a fallback.
_STREAMED_POST_COMMAND_REFRESH_DELAYS: tuple[int, ...] = (10, 60)
# Endpoints that answered UNIMPLEMENTED are skipped on scheduled polls, but
# re-probed this often (seconds) in case the backend starts serving them again.
# Elapsed time rather than a poll count, so it holds if the poll interval changes.
_UNSUPPORTED_REPROBE_INTERVAL = 24 * 60 * 60
# Some endpoints answer INVALID_ARGUMENT on every call for a model that doesn't
# support them. One such answer can be a transient backend hiccup, so only
# this many in a row mark the endpoint unsupported like UNIMPLEMENTED does.
_INVALID_ARGUMENT_UNSUPPORTED_AFTER = 3
# A stream that stops pushing without erroring is indistinguishable from a healthy
# idle one, so resubscribe after this many poll intervals of silence.
_STREAM_STALE_POLL_INTERVALS = 3
_COMMAND_INVOCATION_SUCCESS = {
    InvocationStatus.SENT,
    InvocationStatus.DELIVERED,
    InvocationStatus.SUCCESS,
}
# Coordinator attributes to re-read once a command finishes, keyed by invocation method.
_INVOCATION_REFRESH_ATTRS: dict[str, tuple[str, ...]] = {
    "Lock": ("exterior",),
    "Unlock": ("exterior",),
    "WindowControl": ("exterior",),
    "ClimatizationStart": ("climate",),
    "ClimatizationStop": ("climate",),
    "PreCleaning": ("precleaning",),
}
# The climate status the car reports lags a start command by tens of seconds.
_CLIMATE_START_LAG = 60.0

# Vehicle attribute (False means the car says it lacks the feature) -> names entities depend on.
_CAPABILITY_FETCHES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("supports_charge_locations", ("charge_locations", "current_charge_location")),
    ("supports_window_control", ("window_control",)),
    ("supports_sunroof_control", ("sunroof",)),
    ("supports_target_soc_presets", ("target_soc_presets",)),
    ("reports_avg_consumption", ("avg_consumption",)),
    ("reports_avg_consumption_auto", ("avg_consumption_auto",)),
    ("reports_avg_consumption_since_charge", ("avg_consumption_since_charge",)),
    ("supports_rear_seat_heating", ("rear_seat_heating",)),
)
_CLIMATE_TIMER_SLOTS = 3

# Attributes whose entities are disabled when the first poll succeeds but returns no data at all.
_DISABLE_WHEN_EMPTY = ("precleaning",)

_COMMAND_RESPONSE_STATUS_SUCCESS = {
    ResponseStatusCode.SUCCESS,
    ResponseStatusCode.WARNING,
}


@dataclass
class ClimateCommandPreferences:
    """Preferences used for advanced climate start commands."""

    target_temperature: float = 0.0
    front_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    front_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    steering_wheel: HeatingIntensity = HeatingIntensity.UNSPECIFIED


@dataclass
class PolestarVehicleData:
    """Snapshot of all polled vehicle data."""

    battery: Battery | None = None
    exterior: ExteriorStatus | None = None
    location: Location | None = None
    parked_location: Location | None = None
    climate: ClimatizationInfo | None = None
    dashboard: DashboardStatus | None = None
    health: Health | None = None
    availability: Availability | None = None
    connectivity: ConnectivityInfo | None = None
    odometer: OdometerStatus | None = None
    precleaning: PreCleaningInfo | None = None
    weather: WeatherReport | None = None
    software: CarSoftwareInfo | None = None
    ota_schedule: Scheduler | None = None
    target_soc: TargetSocResponse | None = None
    amp_limit: AmpLimitResponse | None = None
    charge_timer: ChargeTimerResponse | None = None
    charge_locations: list[ChargeLocation] | None = None
    current_charge_location: dict[str, Any] | None = None
    climate_timers: list[ParkingClimateTimer] = field(default_factory=list)
    climate_timer_settings: ParkingClimateTimerSettings | None = None
    remote_function_data_sharing: RemoteFunctionDataSharing | None = None


_FETCH_ATTRS: tuple[tuple[str, str], ...] = (
    ("battery", "get_battery"),
    ("exterior", "get_exterior"),
    ("location", "get_location"),
    ("parked_location", "get_parked_location"),
    ("odometer", "get_odometer"),
    ("climate", "get_climate"),
    ("dashboard", "get_dashboard"),
    ("health", "get_health"),
    ("availability", "get_availability"),
    ("connectivity", "get_connectivity"),
    ("precleaning", "get_precleaning"),
    ("weather", "get_weather"),
    ("software", "get_software_info"),
    ("ota_schedule", "get_ota_schedule"),
    ("target_soc", "get_target_soc"),
    ("amp_limit", "get_amp_limit"),
    ("charge_timer", "get_charge_timer"),
    ("charge_locations", "get_charge_locations"),
    ("current_charge_location", "is_at_charge_location"),
    ("climate_timers", "get_climate_timers"),
    ("climate_timer_settings", "get_climate_timer_settings"),
    ("remote_function_data_sharing", "get_remote_function_data_sharing"),
)
_FETCH_ATTR_LOOKUP = dict(_FETCH_ATTRS)
_ATTR_FIELDS = {spec.name: spec for spec in fields(PolestarVehicleData)}


def _attr_default(attr: str) -> Any:
    """Return the empty PolestarVehicleData value for an attribute."""
    spec = _ATTR_FIELDS[attr]
    if spec.default_factory is not MISSING:
        return spec.default_factory()
    return spec.default


class PolestarCoordinator(DataUpdateCoordinator[PolestarVehicleData]):
    """Coordinator that polls all vehicle data concurrently."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle: Vehicle,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Polestar {vehicle.vin}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
            config_entry=entry,
            always_update=False,
        )
        self.vehicle = vehicle
        self.climate_preferences = ClimateCommandPreferences()
        self._installed_version_cache: str | None = None
        self._stream_tasks: dict[str, asyncio.Task[None]] = {}
        self._unsupported_streams: set[str] = set()
        self._unsupported_commands: set[str] = set()
        self._unsupported_fetches: set[str] = set()
        self._invalid_argument_counts: dict[str, int] = {}
        # What the car says it lacks. Some names are data fetches that are no longer polled; the
        # others are capability names that entities use to say they need the feature.
        for flag, names in _CAPABILITY_FETCHES:
            if getattr(vehicle, flag, None) is False:
                _LOGGER.info("Vehicle %s does not support %s", vehicle.vin, ", ".join(names))
                self._unsupported_fetches.update(names)
        max_timers = getattr(vehicle, "max_climate_timers", None)
        if isinstance(max_timers, int):
            self._unsupported_fetches.update(
                f"climate_timer_slot_{slot}" for slot in range(max_timers + 1, _CLIMATE_TIMER_SLOTS + 1)
            )
        self._empty_fetches: set[str] = set()
        self._no_data_fetches: set[str] = set()
        self._climate_started_at: float | None = None
        self._last_started_values: dict[str, Any] = {}
        self._stream_last_data: dict[str, float] = {}
        self._poll_count: int = 0
        # Polls, post-command refreshes and streams all write here concurrently;
        # a fetch claims a generation before it starts so a slow one can't land
        # after a faster one and resurrect pre-command state.
        self._generation: int = 0
        self._applied_generations: dict[str, int] = {}
        self._last_unsupported_probe: float | None = None
        self._command_failure_listeners: list[Callable[[], None]] = []
        add_listener = getattr(vehicle, "add_invocation_listener", None)
        self._remove_invocation_listener = add_listener(self._handle_invocation_result) if add_listener else None

    def async_add_command_failure_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call *listener* when a command that was accepted later fails; returns an unsubscribe."""
        self._command_failure_listeners.append(listener)

        def remove() -> None:
            if listener in self._command_failure_listeners:
                self._command_failure_listeners.remove(listener)

        return remove

    def _handle_invocation_result(self, method: str, response: Any) -> None:
        """React to the final outcome of a remote command (it returns before the car has acted)."""
        attrs = _INVOCATION_REFRESH_ATTRS.get(method, ())
        if response.status in _COMMAND_INVOCATION_SUCCESS:
            if attrs:
                self._schedule_background_refresh(*attrs)
            return

        reason = response.message or response.status.name.replace("_", " ").lower()
        _LOGGER.warning("Polestar %s command for %s failed: %s", method, self.vehicle.vin, reason)
        persistent_notification.async_create(
            self.hass,
            f"The {method} command was accepted but the car did not complete it: {reason}.",
            title="Polestar command failed",
            notification_id=f"polestar_command_failed_{self.vehicle.vin}_{method}",
        )
        for listener in list(self._command_failure_listeners):
            listener()
        if attrs:
            self._schedule_background_refresh(*attrs)

    @staticmethod
    def _command_succeeded(response: Any) -> bool:
        """Interpret common command response types."""
        # CarLockResponse carries its own failure code alongside a generic
        # invocation status that still reads as success — the car refusing to
        # lock because a door is ajar shows up only here.
        if getattr(response, "lock_error", 0):
            return False

        invocation = getattr(response, "response", None)
        if invocation is not None:
            return invocation.status in _COMMAND_INVOCATION_SUCCESS

        response_status = getattr(response, "response_status", None)
        if response_status is not None:
            return response_status.status in _COMMAND_RESPONSE_STATUS_SUCCESS

        if isinstance(response, int):
            try:
                status = ResponseStatusCode(response)
            except ValueError:
                return False
            return status in _COMMAND_RESPONSE_STATUS_SUCCESS

        return True

    @staticmethod
    def _command_error_message(response: Any, fallback: str) -> str:
        """Build a useful error message from the command response."""
        lock_error = getattr(response, "lock_error", 0)
        if lock_error:
            return f"{fallback} (lock error {lock_error})"

        invocation = getattr(response, "response", None)
        if invocation is not None:
            if invocation.message:
                return invocation.message
            return f"{fallback} ({invocation.status.name.lower()})"

        response_status = getattr(response, "response_status", None)
        if response_status is not None:
            return f"{fallback} ({response_status.status.name.lower()})"

        if isinstance(response, int):
            try:
                status = ResponseStatusCode(response)
            except ValueError:
                return f"{fallback} (status={response})"
            return f"{fallback} ({status.name.lower()})"

        return fallback

    async def async_run_command(
        self,
        command: Callable[[], Awaitable[Any]],
        *,
        error_message: str = "Command failed",
        timeout: int = 30,
        capability: str | None = None,
    ) -> Any:
        """Run a remote command and validate its response.

        If *capability* is set and the server returns FAILED_PRECONDITION or
        UNIMPLEMENTED, the capability is marked as unsupported so entities can
        become unavailable instead of repeatedly failing.
        """
        try:
            response = await asyncio.wait_for(command(), timeout=timeout)
        except TimeoutError:
            raise HomeAssistantError(f"{error_message} (timed out after {timeout}s)")
        except GRPCError as err:
            if capability and err.status in (GrpcStatus.UNIMPLEMENTED, GrpcStatus.FAILED_PRECONDITION):
                self._unsupported_commands.add(capability)
            raise HomeAssistantError(self._command_error_message(err, error_message))
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, error_message))
        return response

    def is_fetch_supported(self, attr: str) -> bool:
        """Return whether the car supports the data behind a coordinator attribute."""
        return attr not in self._unsupported_fetches and attr not in self._no_data_fetches

    def _record_no_data_fetches(self) -> None:
        """After the first poll, remember attributes the car answered with no data at all."""
        self._no_data_fetches = {attr for attr in _DISABLE_WHEN_EMPTY if attr in self._empty_fetches}

    def is_command_supported(self, capability: str) -> bool:
        """Return whether a command capability is supported by the car."""
        return capability not in self._unsupported_commands

    def _schedule_background_refresh(self, *attrs: str) -> None:
        """Kick off a background refresh for the given attributes."""
        label = ",".join(attrs) if attrs else "full"
        self.config_entry.async_create_background_task(
            self.hass,
            self.async_refresh_after_command(*attrs),
            name=f"polestar-{self.vehicle.vin}-{label}-refresh",
        )

    def async_refresh_exterior_after_command(self) -> None:
        """Kick off a background exterior refresh (fallback for when the stream is slow)."""
        self._schedule_background_refresh("exterior")

    @property
    def installed_version_cache(self) -> str | None:
        """Return the best known installed OTA version."""
        return self._installed_version_cache

    @property
    def current_charge_location_details(self) -> ChargeLocation | None:
        """Return the currently active saved charge location, if any."""
        if self.data is None:
            return None
        location_id = (self.data.current_charge_location or {}).get("location_id")
        if not location_id:
            return None
        for location in self.data.charge_locations or ():
            if location.location_id == location_id:
                return location
        return None

    async def _async_fetch_values(
        self,
        attrs: Iterable[str],
        previous: PolestarVehicleData,
        *,
        probe_unsupported: bool = True,
    ) -> tuple[dict[str, Any], int]:
        """Fetch a subset of vehicle attributes concurrently."""
        requested = tuple(dict.fromkeys(attrs))
        values: dict[str, Any] = {}
        if probe_unsupported:
            attr_names = requested
        else:
            attr_names = tuple(a for a in requested if a not in self._unsupported_fetches)
            for attr in self._unsupported_fetches.intersection(requested):
                values[attr] = _attr_default(attr)

        coroutines = [
            asyncio.wait_for(getattr(self.vehicle, _FETCH_ATTR_LOOKUP[attr])(), timeout=15)
            for attr in attr_names
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        successful_fetches = 0
        for attr, result in zip(attr_names, results, strict=True):
            if isinstance(result, (AuthError, TokenExpiredError)):
                raise ConfigEntryAuthFailed(str(result)) from result
            if isinstance(result, BaseException):
                if self._fetch_is_unsupported(attr, result):
                    _LOGGER.info("%s is not supported by vehicle %s; it will not be polled", attr, self.vehicle.vin)
                    self._unsupported_fetches.add(attr)
                    # Clear rather than carry the last good value forward: an
                    # endpoint the backend has withdrawn would otherwise pin
                    # its sensors to a stale snapshot forever.
                    values[attr] = _attr_default(attr)
                    continue
                _LOGGER.debug("Failed to fetch %s for %s: %s", attr, self.vehicle.vin, result)
                values[attr] = getattr(previous, attr)
                continue

            self._invalid_argument_counts.pop(attr, None)
            if attr in self._unsupported_fetches:
                self._unsupported_fetches.discard(attr)
                _LOGGER.info("Fetch %s is supported again for %s", attr, self.vehicle.vin)

            if result is None:
                self._empty_fetches.add(attr)
            else:
                self._empty_fetches.discard(attr)
            result = self._merge_partial_update(attr, getattr(previous, attr), result)
            values[attr] = getattr(previous, attr) if result is None else result
            successful_fetches += 1

        return values, successful_fetches

    def _fetch_is_unsupported(self, attr: str, result: BaseException) -> bool:
        """Whether a failed fetch means the backend does not serve this endpoint."""
        if is_unsupported_feature_error(result):
            return True
        if not (isinstance(result, GRPCError) and result.status is GrpcStatus.INVALID_ARGUMENT):
            return False
        count = self._invalid_argument_counts.get(attr, 0) + 1
        self._invalid_argument_counts[attr] = count
        return count >= _INVALID_ARGUMENT_UNSUPPORTED_AFTER or attr in self._unsupported_fetches

    def next_fetch_generation(self) -> int:
        """Claim the next fetch sequence number.

        Callers take one *before* awaiting their fetch, so results are ordered
        by when they were asked for rather than by when they happened to come
        back. A poll, a post-command refresh and a stream can all finish in
        whatever order the network decides; without this, a poll that started
        before a command could land on top of that command's own refresh and
        resurrect pre-command state.
        """
        self._generation += 1
        return self._generation

    def _claim_unsupported_probe(self) -> bool:
        """Whether this poll should re-probe endpoints that were UNIMPLEMENTED."""
        now = time.monotonic()
        last = self._last_unsupported_probe
        if last is not None and now - last < _UNSUPPORTED_REPROBE_INTERVAL:
            return False
        self._last_unsupported_probe = now
        return True

    async def _async_update_data(self) -> PolestarVehicleData:
        previous = self.data or PolestarVehicleData()
        self._poll_count += 1
        generation = self.next_fetch_generation()
        values, successful_fetches = await self._async_fetch_values(
            _FETCH_ATTR_LOOKUP,
            previous,
            probe_unsupported=self._claim_unsupported_probe(),
        )

        if successful_fetches == 0:
            if self.data is not None:
                return self.data
            raise UpdateFailed("All API calls failed")

        if self.data is None:
            self._record_no_data_fetches()

        # A faster post-command refresh or stream write may have landed for
        # some attrs while this (slower, full) poll was still in flight. Don't
        # let it resurrect what those newer writes already superseded.
        current = self.data
        for attr in values:
            if generation > self._applied_generations.get(attr, 0):
                self._applied_generations[attr] = generation
            elif current is not None:
                values[attr] = getattr(current, attr)

        data = PolestarVehicleData(**values)
        self._update_installed_version_cache(data.software)
        self._unsupported_commands.clear()
        await self._restart_dead_streams()
        return data

    def _async_apply_values(self, values: dict[str, Any], generation: int) -> None:
        """Merge fetched/streamed values into the snapshot and push, generation permitting.

        An attribute is only overwritten by a fetch newer than the one that
        last wrote it, so a slow write cannot resurrect pre-command state on
        top of a faster, newer one. Entities are only notified when a value
        actually changed: a stream replaying its snapshot on every resubscribe
        would otherwise rewrite every entity's state each time.
        """
        if self._apply_values(values, generation):
            self.async_update_listeners()

    def _apply_values(self, values: dict[str, Any], generation: int) -> bool:
        """Merge values into the snapshot; return whether anything changed.

        Sets ``self.data`` directly rather than via ``async_set_updated_data``,
        which would reschedule the next full poll. Streams push roughly every
        minute, so using it here meant the periodic poll never ran and
        poll-only values (target SOC, amp limit, charge timers) went stale.
        """
        if not values:
            return False
        fresh = {
            attr: value
            for attr, value in values.items()
            if generation > self._applied_generations.get(attr, 0)
        }
        if not fresh:
            return False
        for attr in fresh:
            self._applied_generations[attr] = generation

        previous = self.data or PolestarVehicleData()
        changed = {attr: value for attr, value in fresh.items() if getattr(previous, attr) != value}
        if not changed:
            return False

        data = replace(previous, **changed)
        if "software" in changed:
            self._update_installed_version_cache(data.software)
        self.data = data
        self.last_update_success = True
        return True

    async def async_request_attrs_refresh(self, *attrs: str) -> None:
        """Refresh only the requested coordinator attributes."""
        if not attrs:
            await self.async_request_refresh()
            return

        generation = self.next_fetch_generation()
        previous = self.data or PolestarVehicleData()
        # Each command schedules several follow-up refreshes; probing would
        # otherwise call an UNIMPLEMENTED endpoint that many extra times.
        # Re-probing is left to the scheduled once-a-day probe.
        values, successful_fetches = await self._async_fetch_values(
            attrs, previous, probe_unsupported=False
        )
        if successful_fetches == 0:
            return

        self._async_apply_values(values, generation)

    _STREAMS: dict[str, str] = {
        "battery": "stream_battery",
        "location": "stream_location",
        "parked_location": "stream_parked_location",
        "climate": "stream_climate",
        "exterior": "stream_exterior",
        "precleaning": "stream_precleaning",
        "odometer": "stream_odometer",
    }

    async def async_start_streams(self) -> None:
        """Start background stream tasks for live battery/location/exterior/climate updates."""
        if self._stream_tasks:
            return
        for attr, method_name in self._STREAMS.items():
            method = getattr(self.vehicle, method_name, None)
            if method is not None:
                self._stream_tasks[attr] = asyncio.create_task(
                    self._async_run_stream(attr, method),
                    name=f"polestar-{self.vehicle.vin}-{attr}-stream",
                )

    def _stream_running(self, attr: str) -> bool:
        task = self._stream_tasks.get(attr)
        return task is not None and not task.done()

    async def _restart_dead_streams(self) -> None:
        """Restart streams that gave up or went silent, after a poll proves connectivity."""
        stale_after = (
            self.update_interval.total_seconds() * _STREAM_STALE_POLL_INTERVALS
            if self.update_interval is not None
            else None
        )
        now = time.monotonic()
        for attr, method_name in self._STREAMS.items():
            if attr in self._unsupported_streams:
                continue
            task = self._stream_tasks.get(attr)
            if task is not None and not task.done():
                last_data = self._stream_last_data.get(attr)
                # A task that has never yielded may just be a slow first message;
                # only resubscribe when a previously working stream went quiet.
                if stale_after is None or last_data is None or now - last_data < stale_after:
                    continue
                _LOGGER.warning(
                    "Live %s stream for %s delivered nothing for %.0fs, resubscribing",
                    attr, self.vehicle.vin, now - last_data,
                )
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self._stream_last_data.pop(attr, None)
            method = getattr(self.vehicle, method_name, None)
            if method is None:
                continue
            self._stream_tasks[attr] = asyncio.create_task(
                self._async_run_stream(attr, method),
                name=f"polestar-{self.vehicle.vin}-{attr}-stream",
            )

    async def async_shutdown(self) -> None:
        """Cancel any running stream tasks."""
        if self._remove_invocation_listener is not None:
            self._remove_invocation_listener()
            self._remove_invocation_listener = None
        cancel_follow_ups = getattr(self.vehicle, "cancel_invocation_follow_ups", None)
        if cancel_follow_ups is not None:
            await cancel_follow_ups()
        for task in self._stream_tasks.values():
            task.cancel()
        if self._stream_tasks:
            await asyncio.gather(*self._stream_tasks.values(), return_exceptions=True)
        self._stream_tasks.clear()
        self._stream_last_data.clear()
        self._unsupported_streams.clear()
        await super().async_shutdown()

    async def _async_run_stream(
        self,
        attr: str,
        stream_factory: Callable[[], Awaitable[Any] | Any],
    ) -> None:
        """Run a single long-lived stream and merge updates into coordinator state."""
        consecutive_failures = 0
        while True:
            subscribed_at = time.monotonic()
            try:
                received = False
                async for value in stream_factory():
                    received = True
                    consecutive_failures = 0
                    self._stream_last_data[attr] = time.monotonic()
                    current = self.data or PolestarVehicleData()
                    merged_value = self._merge_partial_update(attr, getattr(current, attr), value)
                    self._async_apply_values({attr: merged_value}, self.next_fetch_generation())
                if received:
                    # Server closed a subscription after delivering data (normal
                    # GOAWAY behaviour) — resubscribe, but never sooner than the
                    # floor after the last subscribe, so a server that closes
                    # after every message cannot turn this into a request loop.
                    wait = STREAM_MIN_RESUBSCRIBE_INTERVAL - (time.monotonic() - subscribed_at)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    continue
                # Ended without an error and without a single message: back off,
                # otherwise this becomes an unbounded reconnect loop.
                consecutive_failures += 1
                delay = self._stream_retry_delay(
                    attr, consecutive_failures, RuntimeError("stream closed without data")
                )
                if delay is None:
                    return
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except (AuthError, TokenExpiredError) as err:
                _LOGGER.warning("Live %s stream auth failure for %s: %s", attr, self.vehicle.vin, err)
                await asyncio.sleep(STREAM_RETRY_DELAY)
            except GRPCError as err:
                if err.status == GrpcStatus.UNIMPLEMENTED:
                    _LOGGER.debug("Live %s stream not supported for %s, stopping", attr, self.vehicle.vin)
                    self._unsupported_streams.add(attr)
                    return
                consecutive_failures += 1
                delay = self._stream_retry_delay(attr, consecutive_failures, err)
                if delay is None:
                    return
                await asyncio.sleep(delay)
            except Exception as err:  # noqa: BLE001
                consecutive_failures += 1
                delay = self._stream_retry_delay(attr, consecutive_failures, err)
                if delay is None:
                    return
                await asyncio.sleep(delay)

    def _stream_retry_delay(self, attr: str, failures: int, err: Exception) -> float | None:
        """Return the backoff delay in seconds, or None to stop retrying."""
        if failures >= STREAM_MAX_RETRIES:
            _LOGGER.warning(
                "Live %s stream for %s failed %d times in a row, giving up — "
                "data will still update via polling. "
                "Reload the integration to restart streams",
                attr, self.vehicle.vin, failures,
            )
            return None
        delay = min(STREAM_RETRY_DELAY * (2 ** (failures - 1)), 600)
        _LOGGER.debug("Live %s stream failed for %s (attempt %d): %s — retrying in %ds",
                       attr, self.vehicle.vin, failures, err, delay)
        return delay

    @staticmethod
    def _merge_partial_update(attr: str, previous: Any, result: Any) -> Any:
        """Merge backend partial updates for attrs that are not full snapshots."""
        if result is None:
            return None
        if attr == "exterior" and previous is not None:
            return result.merge(previous)
        if attr == "odometer" and previous is not None:
            # odometer_meters is TOTAL_INCREASING; an out-of-order snapshot from the poll
            # racing the stream would otherwise read as a counter reset in HA statistics.
            # Compare the reading itself rather than a timestamp: a single skewed
            # backend clock would pin the odometer forever, a lower reading cannot.
            if result.odometer_meters < previous.odometer_meters:
                return previous
        return result

    async def async_refresh_after_command(self, *attrs: str) -> None:
        """Refresh after a command, allowing backend state to settle first.

        Stops as soon as any of the attributes differs from what it was when
        the command was issued — the car has reported back, by this refresh or
        by a stream in the meantime. If nothing changes, the whole schedule
        runs as the fallback.
        """
        refresh_attrs = tuple(dict.fromkeys(attrs))
        previous = self.data or PolestarVehicleData()
        before = {attr: getattr(previous, attr) for attr in refresh_attrs}

        def _confirmed() -> bool:
            current = self.data or PolestarVehicleData()
            return any(getattr(current, attr) != value for attr, value in before.items())

        if refresh_attrs and all(self._stream_running(attr) for attr in refresh_attrs):
            delays = _STREAMED_POST_COMMAND_REFRESH_DELAYS
        else:
            delays = _POST_COMMAND_REFRESH_DELAYS
        for delay in delays:
            await asyncio.sleep(delay)
            if _confirmed():
                return
            try:
                if refresh_attrs:
                    await self.async_request_attrs_refresh(*refresh_attrs)
                else:
                    await self.async_request_refresh()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Delayed refresh failed after command for %s (%s): %s",
                    self.vehicle.vin,
                    ",".join(refresh_attrs) if refresh_attrs else "full",
                    err,
                )
            if _confirmed():
                return

    async def async_start_climate(
        self,
        *,
        temperature: float | None = None,
        front_left_seat: HeatingIntensity | None = None,
        front_right_seat: HeatingIntensity | None = None,
        rear_left_seat: HeatingIntensity | None = None,
        rear_right_seat: HeatingIntensity | None = None,
        steering_wheel: HeatingIntensity | None = None,
    ) -> Any:
        """Start climate using command preferences unless explicit values are provided."""
        prefs = self.climate_preferences
        values = {
            "temperature": prefs.target_temperature if temperature is None else temperature,
            "front_left_seat": prefs.front_left_seat if front_left_seat is None else front_left_seat,
            "front_right_seat": prefs.front_right_seat if front_right_seat is None else front_right_seat,
            "rear_left_seat": prefs.rear_left_seat if rear_left_seat is None else rear_left_seat,
            "rear_right_seat": prefs.rear_right_seat if rear_right_seat is None else rear_right_seat,
            "steering_wheel": prefs.steering_wheel if steering_wheel is None else steering_wheel,
        }
        response = await self.vehicle.start_climate(**values)
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, "Start climate command failed"))
        self._climate_started_at = time.monotonic()
        self._last_started_values = values
        self._schedule_background_refresh("climate")
        return response

    @property
    def is_climate_running(self) -> bool:
        """True while the climate is running, or a start was just sent and the car has not reported it yet."""
        climate = self.data.climate if self.data else None
        if climate is not None and climate.is_active:
            return True
        return self._climate_started_at is not None and time.monotonic() - self._climate_started_at < _CLIMATE_START_LAG

    async def async_update_running_climate(self, changed: str) -> None:
        """Apply a changed seat, steering wheel or temperature setting to a running climate.

        Like the Polestar app, this re-sends the start command, which also restarts the
        car's 30 minute timer. Only the setting named by *changed* takes its value from
        the stored preferences; everything else keeps what the car reports (or, just
        after a start the car has not reported yet, what that start sent), so settings
        made in the app are not undone. Does nothing when the climate is not running.
        """
        if not self.is_climate_running:
            return
        prefs = self.climate_preferences
        values: dict[str, Any] = {
            "temperature": prefs.target_temperature,
            "front_left_seat": prefs.front_left_seat,
            "front_right_seat": prefs.front_right_seat,
            "rear_left_seat": prefs.rear_left_seat,
            "rear_right_seat": prefs.rear_right_seat,
            "steering_wheel": prefs.steering_wheel,
        }
        climate = self.data.climate if self.data else None
        if climate is not None and climate.is_active:
            current = {
                "temperature": climate.target_temperature_celsius,
                "front_left_seat": climate.front_left_seat,
                "front_right_seat": climate.front_right_seat,
                "rear_left_seat": climate.rear_left_seat,
                "rear_right_seat": climate.rear_right_seat,
                "steering_wheel": climate.steering_wheel,
            }
            current = {key: value for key, value in current.items() if value is not None}
        else:
            current = dict(self._last_started_values)
        for key, value in current.items():
            if key != changed:
                values[key] = value
        await self.async_start_climate(**values)

    async def async_stop_climate(self) -> Any:
        """Stop climate and refresh state."""
        response = await self.vehicle.stop_climate()
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, "Stop climate command failed"))
        self._climate_started_at = None
        self._schedule_background_refresh("climate")
        return response

    @property
    def target_soc_setting_type(self) -> ChargeTargetLevelSettingType | None:
        """The car's currently active target SoC mode, or None if unknown."""
        if self.data is None or self.data.target_soc is None:
            return None
        setting_type = self.data.target_soc.setting_type
        if setting_type == ChargeTargetLevelSettingType.UNSPECIFIED:
            return None
        return setting_type

    async def async_set_target_soc(self, level: int) -> TargetSocResponse:
        """Set the target SoC level, keeping the car's current mode.

        Never switches mode implicitly — in DAILY/LONG_TRIP the car ignores the
        level and keeps its preset, so this won't override the app's config.
        Use async_set_target_soc_mode to switch mode explicitly.
        """
        mode = self.target_soc_setting_type or ChargeTargetLevelSettingType.CUSTOM
        if mode != ChargeTargetLevelSettingType.CUSTOM:
            # The car ignores a custom level in daily/long-trip mode (it charges to
            # a fixed preset). Tell the user instead of silently snapping back.
            raise HomeAssistantError(
                f"Target SoC is in {mode.name.lower().replace('_', ' ')} mode, which "
                "charges to a fixed preset and ignores a specific level. Set the "
                "'Target SOC mode' select to Custom to choose a specific level."
            )
        response = await self.async_run_command(
            lambda: self.vehicle.set_target_soc(level, mode),
            error_message="Set target SOC command failed",
        )
        self._schedule_background_refresh("target_soc")
        return response

    async def async_set_target_soc_mode(
        self, mode: ChargeTargetLevelSettingType
    ) -> TargetSocResponse:
        """Explicitly switch the car's target SoC mode (daily/long_trip/custom)."""
        level = (
            self.data.target_soc.target_level
            if self.data and self.data.target_soc
            else 0
        )
        response = await self.async_run_command(
            lambda: self.vehicle.set_target_soc(level, mode),
            error_message="Set target SOC mode command failed",
        )
        self._schedule_background_refresh("target_soc")
        return response

    async def async_set_amp_limit(self, amperage: int) -> AmpLimitResponse:
        """Set the charging amperage limit."""
        response = await self.async_run_command(
            lambda: self.vehicle.set_amp_limit(amperage),
            error_message="Set amp limit command failed",
        )
        self._schedule_background_refresh("amp_limit")
        return response

    async def async_start_precleaning(self) -> None:
        """Start cabin pre-cleaning."""
        await self.async_run_command(
            self.vehicle.start_precleaning,
            error_message="Start pre-cleaning command failed",
            capability="precleaning",
        )
        self._schedule_background_refresh("precleaning")

    async def async_stop_precleaning(self) -> None:
        """Stop cabin pre-cleaning."""
        await self.async_run_command(
            self.vehicle.stop_precleaning,
            error_message="Stop pre-cleaning command failed",
            capability="precleaning",
        )
        self._schedule_background_refresh("precleaning")

    async def async_start_charging(self) -> int:
        """Start immediate charging."""
        response = await self.async_run_command(
            self.vehicle.start_charging,
            error_message="Start charging command failed",
            capability="charging",
        )
        self._schedule_background_refresh("battery")
        return response

    async def async_stop_charging(self) -> int:
        """Stop charging."""
        response = await self.async_run_command(
            self.vehicle.stop_charging,
            error_message="Stop charging command failed",
            capability="charging",
        )
        self._schedule_background_refresh("battery")
        return response

    async def async_open_windows(self) -> Any:
        """Open all windows."""
        response = await self.async_run_command(
            self.vehicle.open_windows,
            error_message="Open windows command failed",
            capability="open_windows",
        )
        self._schedule_background_refresh("exterior")
        return response

    async def async_close_windows(self) -> Any:
        """Close all windows."""
        response = await self.async_run_command(
            self.vehicle.close_windows,
            error_message="Close windows command failed",
            capability="close_windows",
        )
        self._schedule_background_refresh("exterior")
        return response

    async def async_unlock_trunk(self) -> Any:
        """Unlock the trunk."""
        response = await self.async_run_command(
            self.vehicle.unlock_trunk,
            error_message="Unlock trunk command failed",
            capability="unlock_trunk",
        )
        self._schedule_background_refresh("exterior")
        return response

    def restore_installed_version_cache(self, version: str) -> None:
        """Restore the installed OTA version cache from HA state."""
        self._installed_version_cache = version

    async def async_set_charge_timer(
        self,
        *,
        start: dt_time | None = None,
        stop: dt_time | None = None,
        activated: bool | None = None,
    ) -> ChargeTimerResponse:
        """Set the global charge timer while preserving unspecified fields."""
        def _daily(t: dt_time) -> DailyTime:
            return DailyTime(
                hour=t.hour,
                minute=t.minute,
                time_zone=TimeZoneOffset(offset_minutes=local_utc_offset_minutes()),
            )

        current_timer = BatteryChargeTimer()
        if self.data and self.data.charge_timer and self.data.charge_timer.timer:
            current_timer = self.data.charge_timer.timer

        timer = BatteryChargeTimer(
            start=current_timer.start if start is None else _daily(start),
            stop=current_timer.stop if stop is None else _daily(stop),
            activated=current_timer.activated if activated is None else activated,
        )
        response = await self.vehicle.set_charge_timer(timer)
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, "Set charge timer command failed"))
        self._schedule_background_refresh("charge_timer")
        return response

    async def async_clear_charge_timer(self) -> ChargeTimerResponse:
        """Disable the global charge timer."""
        return await self.async_set_charge_timer(activated=False)

    async def async_create_charge_location(
        self,
        *,
        alias: str,
        amp_limit: int = 0,
        minimum_soc: int = 0,
        optimised_charging: bool = False,
    ) -> ChargeLocation | None:
        """Create a saved charge location at the car's current location."""
        location = await self.vehicle.create_charge_location(
            alias=alias,
            amp_limit=amp_limit,
            minimum_soc=minimum_soc,
            optimised_charging=optimised_charging,
        )
        self._schedule_background_refresh("charge_locations", "current_charge_location")
        return location

    async def async_update_charge_location(
        self,
        *,
        location_id: str,
        alias: str | None = None,
        amp_limit: int | None = None,
        minimum_soc: int | None = None,
        optimised_charging: bool | None = None,
    ) -> None:
        """Update one or more charge location properties."""
        if alias is not None:
            await self.vehicle.update_charge_location_alias(location_id, alias)
        if amp_limit is not None:
            await self.vehicle.update_charge_location_amp_limit(location_id, amp_limit)
        if minimum_soc is not None:
            await self.vehicle.update_charge_location_min_soc(location_id, minimum_soc)
        if optimised_charging is not None:
            await self.vehicle.update_charge_location_optimised(location_id, optimised_charging)
        self._schedule_background_refresh("charge_locations", "current_charge_location")

    async def async_delete_charge_location(self, location_id: str) -> None:
        """Delete a saved charge location."""
        await self.vehicle.delete_charge_location(location_id)
        self._schedule_background_refresh("charge_locations", "current_charge_location")

    async def async_schedule_ota(self, relative_time: int = 0) -> Scheduler | None:
        """Schedule an OTA update using the currently advertised software id."""
        software_id = self._require_software_id()
        scheduler = await self.vehicle.schedule_ota(software_id, relative_time=relative_time)
        self._schedule_background_refresh("software", "ota_schedule")
        return scheduler

    async def async_install_ota_now(self) -> Scheduler | None:
        """Install the current OTA update immediately."""
        software_id = self._require_software_id()
        scheduler = await self.vehicle.install_ota_now(software_id)
        self._schedule_background_refresh("software", "ota_schedule")
        return scheduler

    async def async_cancel_ota(self) -> Scheduler | None:
        """Cancel any scheduled OTA update."""
        software_id = self._require_software_id()
        scheduler = await self.vehicle.cancel_ota(software_id)
        self._schedule_background_refresh("software", "ota_schedule")
        return scheduler

    async def async_delete_climate_timer(self, timer_id: str) -> None:
        """Delete a parking climate timer."""
        await self.vehicle.delete_climate_timer(timer_id)
        self._schedule_background_refresh("climate_timers")

    async def async_set_climate_timer(self, timer: ParkingClimateTimer) -> int:
        """Create or update a parking climate timer."""
        status = await self.vehicle.set_climate_timer(timer)
        self._schedule_background_refresh("climate_timers")
        return status

    async def async_set_climate_timer_settings(
        self, settings: ParkingClimateTimerSettings,
    ) -> int:
        """Set the default climate settings for parking climate timers."""
        status = await self.vehicle.set_climate_timer_settings(settings)
        self._schedule_background_refresh("climate_timer_settings")
        return status

    def _require_software_id(self) -> str:
        """Return the software id from current state or raise a service-friendly error."""
        software = self.data.software if self.data else None
        if software and software.software_id:
            return software.software_id
        raise HomeAssistantError("No OTA software id is available for this vehicle")

    def _update_installed_version_cache(self, software: CarSoftwareInfo | None) -> None:
        """Track the best known installed version for OTA entity state."""
        if software is None or not software.new_sw_version:
            return
        if software.state in {
            SoftwareState.UNKNOWN,
            SoftwareState.INSTALLATION_COMPLETED,
            SoftwareState.INSTALLATION_UNKNOWN,
        }:
            self._installed_version_cache = software.new_sw_version
