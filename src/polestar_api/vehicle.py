"""Per-vehicle facade."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .models.availability import Availability
from .models.battery import Battery
from .models.charge_location import ChargeLocation
from .models.ota import CarSoftwareInfo, Scheduler
from .models.parking_climate_timer import ParkingClimateTimer, ParkingClimateTimerSettings
from .models.precleaning import PreCleaningInfo
from .models.charging import (
    AmpLimitResponse,
    BatteryChargeTimer,
    ChargeTargetLevelSettingType,
    ChargeTimerResponse,
    TargetSocResponse,
)
from .models.climate import ClimatizationInfo
from .models.climatization import ClimatizationResponse, HeatingIntensity
from .models.common import Location
from .models.connectivity import ConnectivityInfo
from .models.dashboard import DashboardStatus
from .models.exterior import ExteriorStatus
from .models.health import Health
from .models.honkflash import HonkFlashAction, HonkAndFlashResponse
from .models.locks import CarLockResponse, CarUnlockResponse, LockAlarmLevel, LockFeedback, UnlockFeedback, TrunkUnlockResponse
from .models.odometer import OdometerStatus
from .models.wakeup import WakeUpReason, WakeUpResponse
from .models.weather import WeatherReport
from .models.window import WindowControlType
from .services.amp_limit import AmpLimitServiceClient
from .services.availability import AvailabilityServiceClient
from .services.battery import BatteryServiceClient
from .services.charge_location import ChargeLocationServiceClient
from .services.charge_now import ChargeNowServiceClient
from .services.charge_timer import ChargeTimerServiceClient
from .services.climate import ClimateServiceClient
from .services.dashboard import DashboardServiceClient
from .services.exterior import ExteriorServiceClient
from .services.health import HealthServiceClient
from .services.invocation import InvocationServiceClient
from .services.location import LocationServiceClient
from .services.odometer import OdometerServiceClient
from .services.ota import OtaServiceClient
from .services.parking_climate_timer import ParkingClimateTimerServiceClient
from .services.precleaning import PreCleaningServiceClient
from .services.target_soc import TargetSocServiceClient
from .services.weather import WeatherServiceClient

if TYPE_CHECKING:
    from .connection import GrpcConnection


class Vehicle:
    """Represents a single Polestar vehicle."""

    def __init__(
        self,
        vin: str,
        connection: GrpcConnection,
        *,
        internal_id: str | None = None,
        registration_no: str | None = None,
        model_year: int | None = None,
        model_name: str | None = None,
    ) -> None:
        self.vin = vin
        self.internal_id = internal_id
        self.registration_no = registration_no
        self.model_year = model_year
        self.model_name = model_name

        self._amp_limit = AmpLimitServiceClient(connection, vin)
        self._availability = AvailabilityServiceClient(connection, vin)
        self._battery = BatteryServiceClient(connection, vin)
        self._charge_location = ChargeLocationServiceClient(connection, vin)
        self._charge_now = ChargeNowServiceClient(connection, vin)
        self._charge_timer = ChargeTimerServiceClient(connection, vin)
        self._climate = ClimateServiceClient(connection, vin)
        self._dashboard = DashboardServiceClient(connection, vin)
        self._exterior = ExteriorServiceClient(connection, vin)
        self._health = HealthServiceClient(connection, vin)
        self._invocation = InvocationServiceClient(connection, vin)
        self._location = LocationServiceClient(connection, vin)
        self._odometer = OdometerServiceClient(connection, vin)
        self._ota = OtaServiceClient(connection, vin)
        self._parking_climate_timer = ParkingClimateTimerServiceClient(connection, vin)
        self._precleaning = PreCleaningServiceClient(connection, vin)
        self._target_soc = TargetSocServiceClient(connection, vin)
        self._weather = WeatherServiceClient(connection, vin)

    # -- Battery --

    async def get_battery(self) -> Battery | None:
        """Charge level, range, charging status, power, voltage, and temperatures, or ``None`` if unavailable."""
        return await self._battery.get_latest()

    async def stream_battery(self) -> AsyncIterator[Battery]:
        """Real-time battery status updates."""
        async for status in self._battery.stream():
            yield status

    # -- Exterior --

    async def get_exterior(self) -> ExteriorStatus | None:
        """Door, window, sunroof, hood, tailgate, and alarm status, or ``None`` if unavailable."""
        return await self._exterior.get_latest()

    async def stream_exterior(self) -> AsyncIterator[ExteriorStatus]:
        """Real-time exterior status updates (doors, locks, windows)."""
        async for status in self._exterior.stream():
            yield status

    # -- Location --

    async def get_location(self) -> Location:
        """Last known vehicle position."""
        return await self._location.get_last_known()

    async def get_parked_location(self) -> Location:
        """Last parked vehicle position."""
        return await self._location.get_last_parked()

    async def stream_location(self) -> AsyncIterator[Location]:
        """Live position updates."""
        async for loc in self._location.stream_last_known():
            yield loc

    async def stream_parked_location(self) -> AsyncIterator[Location]:
        """Live parked position updates."""
        async for loc in self._location.stream_last_parked():
            yield loc

    # -- Climate --

    async def get_climate(self) -> ClimatizationInfo | None:
        """Climatization running status, request type, and heat/cool action, or ``None`` if unavailable."""
        return await self._climate.get_latest()

    async def stream_climate(self) -> AsyncIterator[ClimatizationInfo]:
        """Live climatization status updates."""
        async for status in self._climate.stream():
            yield status

    async def start_climate(
        self,
        temperature: float = 0.0,
        front_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        front_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        rear_left_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        rear_right_seat: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
        steering_wheel: HeatingIntensity = HeatingIntensity.UNSPECIFIED,
    ) -> ClimatizationResponse:
        """Start climatization with target temperature and optional seat/steering wheel heating."""
        return await self._invocation.climatization_start(
            temperature=temperature,
            front_left_seat=front_left_seat,
            front_right_seat=front_right_seat,
            rear_left_seat=rear_left_seat,
            rear_right_seat=rear_right_seat,
            steering_wheel=steering_wheel,
        )

    async def stop_climate(self) -> ClimatizationResponse:
        """Stop climatization."""
        return await self._invocation.climatization_stop()

    # -- Locks --

    async def lock(
        self,
        feedback: LockFeedback = LockFeedback.NORMAL,
        alarm_level: LockAlarmLevel = LockAlarmLevel.NORMAL,
    ) -> CarLockResponse:
        """Lock the car."""
        return await self._invocation.lock(feedback=feedback, alarm_level=alarm_level)

    async def unlock(self, feedback: UnlockFeedback = UnlockFeedback.NORMAL) -> CarUnlockResponse:
        """Unlock the car."""
        return await self._invocation.unlock(feedback=feedback)

    async def unlock_trunk(self) -> TrunkUnlockResponse:
        """Unlock the trunk."""
        return await self._invocation.trunk_unlock()

    # -- Honk / Flash --

    async def honk_flash(self, action: HonkFlashAction = HonkFlashAction.FLASH) -> HonkAndFlashResponse:
        """Flash lights or honk and flash."""
        return await self._invocation.honk_flash(action=action)

    # -- Dashboard --

    async def get_dashboard(self) -> DashboardStatus | None:
        """Trip meters, odometer, and tyre pressure warnings, or ``None`` if unavailable.

        Note: This is a legacy PCCS endpoint (``DashboardService``).
        It is **UNIMPLEMENTED** on Digital Twin vehicles (Polestar 4+).
        Use :meth:`get_odometer` and :meth:`get_health` instead.
        """
        return await self._dashboard.get_latest()

    async def get_connectivity(self) -> ConnectivityInfo | None:
        """Network status, type, and signal strength, or ``None`` if unavailable.

        Note: Served by the legacy ``DashboardService``. **UNIMPLEMENTED**
        on Digital Twin vehicles (Polestar 4+).
        """
        return await self._dashboard.get_connectivity()

    # -- Odometer --

    async def get_odometer(self) -> OdometerStatus | None:
        """Odometer (meters, converted to km via property), trip meters, and timestamp, or ``None`` if unavailable."""
        return await self._odometer.get_latest()

    # -- Charging --

    async def get_target_soc(self) -> TargetSocResponse:
        """Get the charge target level."""
        return await self._target_soc.get()

    async def set_target_soc(
        self,
        level: int,
        setting_type: ChargeTargetLevelSettingType = ChargeTargetLevelSettingType.CUSTOM,
    ) -> TargetSocResponse:
        """Set the charge target level (0-100%).

        ``DAILY`` and ``LONG_TRIP`` are server-managed presets — the server
        ignores the provided *level* for those setting types and keeps its
        stored preset value.  Use ``CUSTOM`` (default) to apply an arbitrary
        level.
        """
        return await self._target_soc.set(level, setting_type)

    async def get_amp_limit(self) -> AmpLimitResponse:
        """Get the charging amperage limit."""
        return await self._amp_limit.get()

    async def set_amp_limit(self, amperage: int) -> AmpLimitResponse:
        """Set the charging amperage limit."""
        return await self._amp_limit.set(amperage)

    async def get_charge_timer(self) -> ChargeTimerResponse:
        """Get the scheduled charge timer."""
        return await self._charge_timer.get()

    async def set_charge_timer(self, timer: BatteryChargeTimer) -> ChargeTimerResponse:
        """Set a scheduled charge timer."""
        return await self._charge_timer.set(timer)

    # -- Wake-up --

    async def wakeup(self, reason: WakeUpReason = WakeUpReason.UNDEFINED) -> WakeUpResponse:
        """Wake the car from sleep."""
        return await self._invocation.wakeup(reason=reason)

    # -- Health --

    async def get_health(self) -> Health | None:
        """Service warnings, brake fluid, tyre pressures (kPa), and tyre pressure warnings, or ``None`` if unavailable.

        Note: On EVs (Polestar 4), engine coolant, oil level, washer fluid,
        low-voltage battery, and all exterior light warning fields are not
        reported by the backend and will be their default (UNSPECIFIED/0).
        """
        return await self._health.get_latest()

    # -- Availability --

    async def get_availability(self) -> Availability | None:
        """Vehicle online status and unavailable reason (power saving, OTA, in use, etc.), or ``None`` if unavailable."""
        return await self._availability.get_latest()

    # -- Windows --

    async def open_windows(self) -> ClimatizationResponse:
        """Open all windows."""
        return await self._invocation.window_control(WindowControlType.OPEN_ALL)

    async def close_windows(self) -> ClimatizationResponse:
        """Close all windows."""
        return await self._invocation.window_control(WindowControlType.CLOSE_ALL)

    # -- Charge Now --

    async def start_charging(self) -> int:
        """Start charging immediately."""
        return await self._charge_now.start()

    async def stop_charging(self) -> int:
        """Stop charging."""
        return await self._charge_now.stop()

    # -- Charge Locations --

    async def get_charge_locations(self) -> list[ChargeLocation]:
        """Saved charge locations with per-location settings (amp limit, min SOC, timers, departure times)."""
        return await self._charge_location.get_locations()

    async def is_at_charge_location(self) -> dict:
        """Check if parked at a saved charge location."""
        return await self._charge_location.is_at_location()

    async def create_charge_location(
        self,
        alias: str,
        amp_limit: int = 0,
        minimum_soc: int = 0,
        optimised_charging: bool = False,
    ) -> ChargeLocation | None:
        """Save the current position as a charge location."""
        return await self._charge_location.create_at_car_location(
            alias, amp_limit, minimum_soc, optimised_charging,
        )

    async def update_charge_location_alias(self, location_id: str, alias: str) -> int:
        """Rename a saved charge location."""
        return await self._charge_location.update_alias(location_id, alias)

    async def update_charge_location_amp_limit(self, location_id: str, amp_limit: int) -> int:
        """Set the amp limit for a saved charge location."""
        return await self._charge_location.update_amp_limit(location_id, amp_limit)

    async def update_charge_location_min_soc(self, location_id: str, minimum_soc: int) -> int:
        """Set the minimum SOC for a saved charge location."""
        return await self._charge_location.update_minimum_soc(location_id, minimum_soc)

    async def update_charge_location_optimised(self, location_id: str, enabled: bool) -> int:
        """Enable or disable smart charging at a saved location."""
        return await self._charge_location.update_optimised_charging(location_id, enabled)

    async def delete_charge_location(self, location_id: str) -> int:
        """Delete a saved charge location."""
        return await self._charge_location.delete_location(location_id)

    # -- Weather --

    async def get_weather(self) -> WeatherReport | None:
        """Temperature at the car's current location, or ``None`` if unavailable."""
        return await self._weather.get_report()

    # -- OTA --

    async def get_software_info(self) -> CarSoftwareInfo | None:
        """Current software version and update state.

        Returns ``None`` when no software info is available from the backend
        (observed on Polestar 4 when no OTA update is pending).
        """
        return await self._ota.get_software_info()

    async def get_ota_schedule(self) -> Scheduler | None:
        """Scheduled OTA update info."""
        return await self._ota.get_schedule()

    async def schedule_ota(self, software_id: str, relative_time: int = 0) -> Scheduler | None:
        """Schedule an OTA update. relative_time is seconds from now."""
        return await self._ota.schedule(software_id, relative_time)

    async def install_ota_now(self, software_id: str) -> Scheduler | None:
        """Install an OTA update immediately."""
        return await self._ota.install_now(software_id)

    async def cancel_ota(self, software_id: str) -> Scheduler | None:
        """Cancel a scheduled OTA update."""
        return await self._ota.cancel_schedule(software_id)

    # -- Parking Climate Timers --

    async def get_climate_timers(self) -> list[ParkingClimateTimer]:
        """Get all scheduled parking climate timers."""
        return await self._parking_climate_timer.get_timers()

    async def set_climate_timer(self, timer: ParkingClimateTimer) -> int:
        """Create or update a scheduled parking climate timer."""
        return await self._parking_climate_timer.set_timer(timer)

    async def delete_climate_timer(self, timer_id: str) -> int:
        """Delete a scheduled parking climate timer."""
        return await self._parking_climate_timer.delete_timer(timer_id)

    async def get_climate_timer_settings(self) -> ParkingClimateTimerSettings:
        """Get the default climate settings applied when a parking climate timer fires."""
        return await self._parking_climate_timer.get_timer_settings()

    async def set_climate_timer_settings(self, settings: ParkingClimateTimerSettings) -> int:
        """Set the default climate settings for parking climate timers."""
        return await self._parking_climate_timer.set_timer_settings(settings)

    # -- Pre-cleaning --

    async def get_precleaning(self) -> PreCleaningInfo | None:
        """Air quality status, PM2.5 levels, running state, and runtime remaining.

        Returns ``None`` when the backend sends an empty pre-cleaning payload.
        """
        return await self._precleaning.get_latest()

    async def stream_precleaning(self) -> AsyncIterator[PreCleaningInfo]:
        """Real-time pre-cleaning status updates."""
        async for status in self._precleaning.stream():
            yield status

    async def start_precleaning(self) -> None:
        """Start cabin air quality pre-cleaning."""
        await self._invocation.precleaning_start()

    async def stop_precleaning(self) -> None:
        """Stop cabin air quality pre-cleaning."""
        await self._invocation.precleaning_stop()

    def __repr__(self) -> str:
        parts = [f"Vehicle(vin={self.vin!r}"]
        if self.model_name:
            parts.append(f", model={self.model_name!r}")
        if self.model_year:
            parts.append(f", year={self.model_year}")
        parts.append(")")
        return "".join(parts)
