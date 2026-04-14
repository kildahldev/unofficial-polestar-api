"""DataUpdateCoordinator for Polestar vehicles."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import time as dt_time, timedelta
from typing import TYPE_CHECKING, Any

from grpclib.const import Status as GrpcStatus
from grpclib.exceptions import GRPCError
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from polestar_api.exceptions import AuthError, TokenExpiredError
from polestar_api.models.availability import Availability
from polestar_api.models.battery import Battery
from polestar_api.models.charge_location import ChargeLocation
from polestar_api.models.charging import (
    AmpLimitResponse,
    BatteryChargeTimer,
    ChargeTargetLevelSettingType,
    ChargeTimerResponse,
    TargetSocResponse,
)
from polestar_api.models.climate import ClimatizationInfo
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.models.common import Location, ResponseStatusCode
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

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, STREAM_MAX_RETRIES, STREAM_RETRY_DELAY
from .utils import local_utc_offset_minutes, time_to_minutes

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from polestar_api.vehicle import Vehicle

_LOGGER = logging.getLogger(__name__)
_POST_COMMAND_REFRESH_DELAYS: tuple[int, ...] = (3, 5)
_COMMAND_INVOCATION_SUCCESS = {
    InvocationStatus.SENT,
    InvocationStatus.DELIVERED,
    InvocationStatus.SUCCESS,
}
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
    charge_locations: list[ChargeLocation] = field(default_factory=list)
    current_charge_location: dict[str, Any] = field(default_factory=dict)
    climate_timers: list[ParkingClimateTimer] = field(default_factory=list)
    climate_timer_settings: ParkingClimateTimerSettings | None = None


_FETCH_ATTRS: tuple[tuple[str, str], ...] = (
    ("battery", "get_battery"),
    ("exterior", "get_exterior"),
    ("location", "get_location"),
    ("parked_location", "get_parked_location"),
    ("climate", "get_climate"),
    ("dashboard", "get_dashboard"),
    ("health", "get_health"),
    ("availability", "get_availability"),
    ("connectivity", "get_connectivity"),
    ("odometer", "get_odometer"),
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
)
_FETCH_ATTR_LOOKUP = dict(_FETCH_ATTRS)


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
        )
        self.vehicle = vehicle
        self.climate_preferences = ClimateCommandPreferences()
        self.target_soc_setting_type = ChargeTargetLevelSettingType.DAILY
        self._installed_version_cache: str | None = None
        self._stream_tasks: dict[str, asyncio.Task[None]] = {}

    @staticmethod
    def _command_succeeded(response: Any) -> bool:
        """Interpret common command response types."""
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
    ) -> Any:
        """Run a remote command and validate its response."""
        try:
            response = await asyncio.wait_for(command(), timeout=timeout)
        except TimeoutError:
            raise HomeAssistantError(f"{error_message} (timed out after {timeout}s)")
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, error_message))
        return response

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
        location_id = self.data.current_charge_location.get("location_id")
        if not location_id:
            return None
        for location in self.data.charge_locations:
            if location.location_id == location_id:
                return location
        return None

    async def _async_fetch_values(
        self,
        attrs: Iterable[str],
        previous: PolestarVehicleData,
    ) -> tuple[dict[str, Any], int]:
        """Fetch a subset of vehicle attributes concurrently."""
        attr_names = tuple(dict.fromkeys(attrs))
        coroutines = [
            asyncio.wait_for(getattr(self.vehicle, _FETCH_ATTR_LOOKUP[attr])(), timeout=15)
            for attr in attr_names
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        values: dict[str, Any] = {}
        successful_fetches = 0
        for attr, result in zip(attr_names, results, strict=True):
            if isinstance(result, (AuthError, TokenExpiredError)):
                raise ConfigEntryAuthFailed(str(result)) from result
            if isinstance(result, Exception):
                _LOGGER.debug("Failed to fetch %s for %s: %s", attr, self.vehicle.vin, result)
                values[attr] = getattr(previous, attr)
                continue

            result = self._merge_partial_update(attr, getattr(previous, attr), result)
            values[attr] = getattr(previous, attr) if result is None else result
            successful_fetches += 1

        return values, successful_fetches

    async def _async_update_data(self) -> PolestarVehicleData:
        previous = self.data or PolestarVehicleData()
        values, successful_fetches = await self._async_fetch_values(_FETCH_ATTR_LOOKUP, previous)

        if successful_fetches == 0:
            if self.data is not None:
                return self.data
            raise UpdateFailed("All API calls failed")

        data = PolestarVehicleData(**values)
        self._update_installed_version_cache(data.software)
        return data

    async def async_request_attrs_refresh(self, *attrs: str) -> None:
        """Refresh only the requested coordinator attributes."""
        if not attrs:
            await self.async_request_refresh()
            return

        previous = self.data or PolestarVehicleData()
        values, successful_fetches = await self._async_fetch_values(attrs, previous)
        if successful_fetches == 0:
            return

        data = replace(previous, **values)
        if "software" in values:
            self._update_installed_version_cache(data.software)
        self.async_set_updated_data(data)

    async def async_start_streams(self) -> None:
        """Start background stream tasks for live battery/location/exterior/climate updates."""
        if self._stream_tasks:
            return

        streams = {
            "battery": "stream_battery",
            "location": "stream_location",
            "climate": "stream_climate",
            "exterior": "stream_exterior",
            "precleaning": "stream_precleaning",
        }
        for attr, method_name in streams.items():
            method = getattr(self.vehicle, method_name, None)
            if method is not None:
                self._stream_tasks[attr] = asyncio.create_task(
                    self._async_run_stream(attr, method),
                    name=f"polestar-{self.vehicle.vin}-{attr}-stream",
                )

    async def async_shutdown(self) -> None:
        """Cancel any running stream tasks."""
        for task in self._stream_tasks.values():
            task.cancel()
        if self._stream_tasks:
            await asyncio.gather(*self._stream_tasks.values(), return_exceptions=True)
        self._stream_tasks.clear()

    async def _async_run_stream(
        self,
        attr: str,
        stream_factory: Callable[[], Awaitable[Any] | Any],
    ) -> None:
        """Run a single long-lived stream and merge updates into coordinator state."""
        consecutive_failures = 0
        while True:
            try:
                async for value in stream_factory():
                    consecutive_failures = 0
                    current = self.data or PolestarVehicleData()
                    merged_value = self._merge_partial_update(attr, getattr(current, attr), value)
                    self.async_set_updated_data(replace(current, **{attr: merged_value}))
            except asyncio.CancelledError:
                raise
            except (AuthError, TokenExpiredError) as err:
                _LOGGER.warning("Live %s stream auth failure for %s: %s", attr, self.vehicle.vin, err)
                await asyncio.sleep(STREAM_RETRY_DELAY)
            except GRPCError as err:
                if err.status == GrpcStatus.UNIMPLEMENTED:
                    _LOGGER.debug("Live %s stream not supported for %s, stopping", attr, self.vehicle.vin)
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
        return result

    async def async_refresh_after_command(self, *attrs: str) -> None:
        """Refresh after a command, allowing backend state to settle first."""
        refresh_attrs = tuple(dict.fromkeys(attrs))
        for delay in _POST_COMMAND_REFRESH_DELAYS:
            await asyncio.sleep(delay)
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
        response = await self.vehicle.start_climate(
            temperature=prefs.target_temperature if temperature is None else temperature,
            front_left_seat=prefs.front_left_seat if front_left_seat is None else front_left_seat,
            front_right_seat=prefs.front_right_seat if front_right_seat is None else front_right_seat,
            rear_left_seat=prefs.rear_left_seat if rear_left_seat is None else rear_left_seat,
            rear_right_seat=prefs.rear_right_seat if rear_right_seat is None else rear_right_seat,
            steering_wheel=prefs.steering_wheel if steering_wheel is None else steering_wheel,
        )
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, "Start climate command failed"))
        self._schedule_background_refresh("climate")
        return response

    async def async_stop_climate(self) -> Any:
        """Stop climate and refresh state."""
        response = await self.vehicle.stop_climate()
        if not self._command_succeeded(response):
            raise HomeAssistantError(self._command_error_message(response, "Stop climate command failed"))
        self._schedule_background_refresh("climate")
        return response

    async def async_set_target_soc(self, level: int) -> TargetSocResponse:
        """Set target SoC using the selected setting type."""
        response = await self.async_run_command(
            lambda: self.vehicle.set_target_soc(level, self.target_soc_setting_type),
            error_message="Set target SOC command failed",
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
        )
        self._schedule_background_refresh("precleaning")

    async def async_stop_precleaning(self) -> None:
        """Stop cabin pre-cleaning."""
        await self.async_run_command(
            self.vehicle.stop_precleaning,
            error_message="Stop pre-cleaning command failed",
        )
        self._schedule_background_refresh("precleaning")

    async def async_start_charging(self) -> int:
        """Start immediate charging."""
        response = await self.async_run_command(
            self.vehicle.start_charging,
            error_message="Start charging command failed",
        )
        self._schedule_background_refresh("battery")
        return response

    async def async_stop_charging(self) -> int:
        """Stop charging."""
        response = await self.async_run_command(
            self.vehicle.stop_charging,
            error_message="Stop charging command failed",
        )
        self._schedule_background_refresh("battery")
        return response

    async def async_open_windows(self) -> Any:
        """Open all windows."""
        response = await self.async_run_command(
            self.vehicle.open_windows,
            error_message="Open windows command failed",
        )
        self._schedule_background_refresh("exterior")
        return response

    async def async_close_windows(self) -> Any:
        """Close all windows."""
        response = await self.async_run_command(
            self.vehicle.close_windows,
            error_message="Close windows command failed",
        )
        self._schedule_background_refresh("exterior")
        return response

    async def async_unlock_trunk(self) -> Any:
        """Unlock the trunk."""
        response = await self.async_run_command(
            self.vehicle.unlock_trunk,
            error_message="Unlock trunk command failed",
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
        current_timer = BatteryChargeTimer(timezone_offset=local_utc_offset_minutes())
        if self.data and self.data.charge_timer and self.data.charge_timer.timer:
            current_timer = self.data.charge_timer.timer

        timer = BatteryChargeTimer(
            start=current_timer.start if start is None else time_to_minutes(start),
            stop=current_timer.stop if stop is None else time_to_minutes(stop),
            activated=current_timer.activated if activated is None else activated,
            timezone_offset=local_utc_offset_minutes(),
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
