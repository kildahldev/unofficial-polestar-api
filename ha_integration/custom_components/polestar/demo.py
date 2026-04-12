"""Dummy vehicle for testing without API access."""

from __future__ import annotations

import asyncio
import math
from dataclasses import replace
import logging
import random

from polestar_api.models.availability import (
    Availability,
    AvailabilityStatus,
    UnavailableReason,
    UsageMode,
)
from polestar_api.models.battery import (
    Battery,
    ChargerConnectionStatus,
    ChargerPowerStatus,
    ChargingStatus,
    ChargingType,
)
from polestar_api.models.charge_location import ChargeLocation, ChargeLocationType, OptimisedChargingType
from polestar_api.models.charging import (
    AmpLimitResponse,
    BatteryChargeTimer,
    ChargeTargetLevelSettingType,
    ChargeTimerResponse,
    TargetSocResponse,
)
from polestar_api.models.climate import (
    ClimatizationInfo,
    ClimatizationRequestType,
    ClimatizationRunningStatus,
    HeatOrCoolAction,
)
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.models.common import Coordinate, ResponseStatus, ResponseStatusCode, Timestamp, Weekday
from polestar_api.models.common import Location
from polestar_api.models.connectivity import ConnectivityInfo, ConnectivityStatus, NetworkType, SignalStrength
from polestar_api.models.dashboard import CarDashboardData, DashboardStatus
from polestar_api.models.exterior import (
    CentralLockStatus,
    DoorStatus,
    DoorsStatus,
    ExteriorStatus,
    HoodStatus,
    LockStatus,
    OpenStatus,
    SunroofStatus,
    TailgateStatus,
    TankLidStatus,
    WindowsStatus,
    WindowStatus,
)
from polestar_api.models.health import (
    BrakeFluidLevelWarning,
    EngineCoolantLevelWarning,
    Health,
    LowVoltageBatteryWarning,
    OilLevelWarning,
    ServiceWarning,
    WasherFluidLevelWarning,
)
from polestar_api.models.ota import CarSoftwareInfo, ScheduleInfo, ScheduleSetBy, ScheduleStatus, Scheduler, SoftwareState
from polestar_api.models.parking_climate_timer import (
    BatteryPreconditioning,
    ParkingClimateTimer,
    ParkingClimateTimerSettings,
    SeatHeatingSettings,
)
from polestar_api.models.precleaning import (
    PreCleaningErrorType,
    PreCleaningInfo,
    PreCleaningRunningStatus,
    PreCleaningStartReason,
)
from polestar_api.models.weather import WeatherReport

_LOGGER = logging.getLogger(__name__)

_CLOSED = DoorStatus(lock_status=LockStatus.LOCKED, open_status=OpenStatus.CLOSED)
_NOW = Timestamp(seconds=1743550000, nanos=0)


class DemoVehicle:
    """Fake vehicle that returns static data. Quacks like polestar_api.Vehicle."""

    def __init__(self) -> None:
        self.vin = "DEMO00000PS4TEST1"
        self.internal_id = "demo-internal-id"
        self.registration_no = "DEMO 001"
        self.model_year = 2026
        self.model_name = "Polestar 4"

        self._locked = True
        self._climate_on = False
        self._charging = True
        self._charge_level = 72.0
        self._precleaning_on = False
        self._windows_open = False
        self._tailgate_open = False
        self._target_soc = 80
        self._target_soc_setting_type = ChargeTargetLevelSettingType.DAILY
        self._amp_limit = 16
        self._charge_timer = BatteryChargeTimer(start=1320, stop=360, activated=False, timezone_offset=60)
        self._charge_locations = [
            ChargeLocation(
                location_id="home",
                location_alias="Home",
                latitude=59.9139,
                longitude=10.7522,
                amp_limit=16,
                minimum_soc=40,
                is_optimised_charging_enabled=True,
                available_optimised_charging=OptimisedChargingType.INTELLIGENT_TIMER,
                location_type=ChargeLocationType.SAVED,
            )
        ]
        self._current_charge_location_id = "home"
        self._software_info = CarSoftwareInfo(
            software_id="demo-ota-1",
            new_sw_version="P2.8.1",
            state=SoftwareState.INSTALLATION_COMPLETED,
            schedule_info=ScheduleInfo(scheduled_at=_NOW),
        )
        self._ota_schedule = Scheduler(
            status=ScheduleStatus.IDLE,
            software_id="demo-ota-1",
            scheduled_time=_NOW,
            set_by=ScheduleSetBy.APP,
        )
        self._climate_timers = [
            ParkingClimateTimer(
                timer_id="timer-1",
                index=0,
                ready_at_hour=7,
                ready_at_minute=30,
                activated=True,
                repeat=True,
                weekdays=(Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY, Weekday.THURSDAY, Weekday.FRIDAY),
            ),
            ParkingClimateTimer(
                timer_id="timer-2",
                index=1,
                ready_at_hour=16,
                ready_at_minute=45,
                activated=False,
                repeat=False,
                weekdays=(),
            ),
        ]
        self._climate_timer_settings = ParkingClimateTimerSettings(
            seat_heating=SeatHeatingSettings(
                front_left=HeatingIntensity.LEVEL2,
                front_right=HeatingIntensity.LEVEL2,
            ),
            steering_wheel_heating=HeatingIntensity.LEVEL1,
            temperature_celsius=22.0,
            is_temperature_requested=True,
            battery_preconditioning=BatteryPreconditioning.WHEN_PLUGGED,
        )

    async def stream_battery(self):
        """Simulate battery draining while driving, charging when plugged in."""
        while True:
            if self._charging:
                self._charge_level = min(100.0, self._charge_level + 0.5)
            else:
                self._charge_level = max(5.0, self._charge_level - 0.3)
            yield await self.get_battery()
            await asyncio.sleep(30)

    async def get_battery(self) -> Battery:
        range_km = self._charge_level * 4.8  # ~480km at 100%
        return Battery(
            timestamp=_NOW,
            charge_level=round(self._charge_level, 1),
            avg_consumption=18.4,
            range_km=round(range_km, 1),
            time_to_full=int((100.0 - self._charge_level) * 2) if self._charging else 0,
            charger_connection_status=(
                ChargerConnectionStatus.CONNECTED if self._charging
                else ChargerConnectionStatus.DISCONNECTED
            ),
            charging_status=(
                ChargingStatus.CHARGING if self._charging
                else ChargingStatus.IDLE
            ),
            range_miles=round(range_km * 0.621, 1),
            time_to_target=int((self._target_soc - self._charge_level) * 2) if self._charging and self._charge_level < self._target_soc else 0,
            power_watts=7400 if self._charging else 0,
            current_amps=32 if self._charging else 0,
            voltage_volts=230 if self._charging else 0,
            charging_type=ChargingType.AC if self._charging else ChargingType.NONE,
            charger_power_status=(
                ChargerPowerStatus.PROVIDING_POWER if self._charging
                else ChargerPowerStatus.NO_POWER
            ),
            avg_consumption_auto=18.1,
            avg_consumption_since_charge=17.9,
            time_to_min_soc=0,
        )

    async def get_exterior(self) -> ExteriorStatus:
        lock = LockStatus.LOCKED if self._locked else LockStatus.UNLOCKED
        window_status = OpenStatus.OPEN if self._windows_open else OpenStatus.CLOSED
        tailgate_status = OpenStatus.OPEN if self._tailgate_open else OpenStatus.CLOSED
        return ExteriorStatus(
            central_lock=CentralLockStatus(lock_status=lock),
            doors=DoorsStatus(
                front_left=DoorStatus(lock_status=lock, open_status=OpenStatus.CLOSED),
                front_right=DoorStatus(lock_status=lock, open_status=OpenStatus.CLOSED),
                rear_left=DoorStatus(lock_status=lock, open_status=OpenStatus.CLOSED),
                rear_right=DoorStatus(lock_status=lock, open_status=OpenStatus.CLOSED),
            ),
            windows=WindowsStatus(
                front_left=WindowStatus(open_status=window_status),
                front_right=WindowStatus(open_status=window_status),
                rear_left=WindowStatus(open_status=window_status),
                rear_right=WindowStatus(open_status=window_status),
            ),
            sunroof=SunroofStatus(open_status=OpenStatus.CLOSED),
            hood=HoodStatus(status=_CLOSED),
            tailgate=TailgateStatus(
                status=DoorStatus(lock_status=lock, open_status=tailgate_status),
            ),
            tank_lid=TankLidStatus(open_status=OpenStatus.CLOSED),
        )

    async def stream_exterior(self):
        """Stream the current exterior state for live demo updates."""
        while True:
            yield await self.get_exterior()
            await asyncio.sleep(30)

    async def get_location(self) -> Location:
        return Location(
            timestamp=_NOW,
            coordinate=Coordinate(latitude=59.9139, longitude=10.7522),
            altitude=15,
            heading=180,
            speed=0,
        )

    async def stream_location(self):
        """Simulate a drive loop around central Oslo."""
        # Circle around Oslo centre, ~1km radius
        centre_lat, centre_lon = 59.9139, 10.7522
        radius_lat = 0.005
        radius_lon = 0.008
        step = 0
        while True:
            angle = math.radians(step * 6)  # 6 degrees per tick = full circle in 60 steps
            lat = centre_lat + radius_lat * math.sin(angle)
            lon = centre_lon + radius_lon * math.cos(angle)
            heading = (step * 6) % 360
            yield Location(
                timestamp=_NOW,
                coordinate=Coordinate(latitude=round(lat, 6), longitude=round(lon, 6)),
                altitude=15,
                heading=heading,
                speed=random.randint(20, 50),
            )
            step += 1
            await asyncio.sleep(30)

    async def get_parked_location(self) -> Location:
        return Location(
            timestamp=_NOW,
            coordinate=Coordinate(latitude=59.9132, longitude=10.7515),
            altitude=15,
            heading=0,
            speed=0,
        )

    async def get_climate(self) -> ClimatizationInfo:
        if self._climate_on:
            return ClimatizationInfo(
                running_status=ClimatizationRunningStatus.ACTIVE,
                request_type=ClimatizationRequestType.NOW_FROM_REMOTE,
                time_remaining=25,
                heat_or_cool_action=HeatOrCoolAction.HEATING,
            )
        return ClimatizationInfo(
            running_status=ClimatizationRunningStatus.IDLE,
            request_type=ClimatizationRequestType.NO_REQUEST,
        )

    async def stream_climate(self):
        """Stream the current climate state for live demo updates."""
        while True:
            yield await self.get_climate()
            await asyncio.sleep(30)

    async def get_dashboard(self) -> DashboardStatus:
        return DashboardStatus(
            dashboard_data=CarDashboardData(
                odometer_km=12450.0,
                trip_meter_manual_km=234.5,
                trip_meter_auto_km=89.1,
            ),
        )

    async def get_health(self) -> Health:
        return Health(
            timestamp=_NOW,
            engine_hours_to_service=120,
            days_to_service=142,
            distance_to_service_km=8500,
            service_warning=ServiceWarning.NO_WARNING,
            brake_fluid_level_warning=BrakeFluidLevelWarning.NO_WARNING,
            engine_coolant_level_warning=EngineCoolantLevelWarning.NO_WARNING,
            oil_level_warning=OilLevelWarning.NO_WARNING,
            washer_fluid_level_warning=WasherFluidLevelWarning.NO_WARNING,
            low_voltage_battery_warning=LowVoltageBatteryWarning.NO_WARNING,
            front_left_tyre_pressure_kpa=248.0,
            front_right_tyre_pressure_kpa=251.0,
            rear_left_tyre_pressure_kpa=262.0,
            rear_right_tyre_pressure_kpa=259.0,
        )

    async def get_availability(self) -> Availability:
        return Availability(
            timestamp=_NOW,
            availability_status=AvailabilityStatus.AVAILABLE,
            unavailable_reason=UnavailableReason.UNSPECIFIED,
            usage_mode=UsageMode.INACTIVE,
        )

    async def get_connectivity(self) -> ConnectivityInfo:
        return ConnectivityInfo(
            status=ConnectivityStatus.CONNECTED,
            network_type=NetworkType.LTE,
            signal_strength=SignalStrength.STRONG,
        )

    async def get_odometer(self):
        from polestar_api.models.odometer import OdometerStatus

        return OdometerStatus(odometer_km=12450.0)

    async def get_precleaning(self) -> PreCleaningInfo:
        return PreCleaningInfo(
            timestamp=_NOW,
            running_status=(
                PreCleaningRunningStatus.ON if self._precleaning_on
                else PreCleaningRunningStatus.OFF
            ),
            start_reason=PreCleaningStartReason.REMOTE if self._precleaning_on else PreCleaningStartReason.UNSPECIFIED,
            measured_air_quality_index=42,
            measured_particulate_matter_2_5=8,
            runtime_left_minutes=12 if self._precleaning_on else 0,
            error=PreCleaningErrorType.UNSPECIFIED,
        )

    async def get_weather(self) -> WeatherReport:
        return WeatherReport(
            temperature_celsius=14.0 + random.uniform(-0.5, 0.5),
        )

    async def get_software_info(self) -> CarSoftwareInfo:
        return self._software_info

    async def get_ota_schedule(self) -> Scheduler:
        return self._ota_schedule

    async def get_target_soc(self) -> TargetSocResponse:
        return TargetSocResponse(
            response_status=ResponseStatus(status=ResponseStatusCode.SUCCESS),
            target_level=self._target_soc,
        )

    async def get_amp_limit(self) -> AmpLimitResponse:
        return AmpLimitResponse(
            response_status=ResponseStatus(status=ResponseStatusCode.SUCCESS),
            amperage_limit=self._amp_limit,
        )

    async def get_charge_timer(self) -> ChargeTimerResponse:
        return ChargeTimerResponse(
            response_status=ResponseStatus(status=ResponseStatusCode.SUCCESS),
            timer=self._charge_timer,
        )

    async def get_charge_locations(self) -> list[ChargeLocation]:
        return list(self._charge_locations)

    async def is_at_charge_location(self) -> dict:
        if self._current_charge_location_id is None:
            return {}
        return {"location_id": self._current_charge_location_id, "arrived_at": _NOW.seconds}

    async def get_climate_timers(self) -> list[ParkingClimateTimer]:
        return list(self._climate_timers)

    async def set_climate_timer(self, timer: ParkingClimateTimer) -> int:
        existing = next((item for item in self._climate_timers if item.timer_id == timer.timer_id), None)
        if existing is None:
            if len(self._climate_timers) >= 3:
                raise ValueError("Maximum number of parking climate timers reached")
            next_index = max((item.index for item in self._climate_timers), default=-1) + 1
            stored = replace(timer, timer_id=f"timer-{len(self._climate_timers) + 1}", index=next_index)
            self._climate_timers.append(stored)
        else:
            stored = replace(timer, timer_id=existing.timer_id, index=existing.index)
            self._climate_timers = [
                stored if item.timer_id == existing.timer_id else item
                for item in self._climate_timers
            ]
        self._climate_timers.sort(key=lambda item: item.index)
        return 3

    async def lock(self, **kwargs) -> None:
        _LOGGER.info("Demo: lock")
        self._locked = True
        self._tailgate_open = False

    async def unlock(self, **kwargs) -> None:
        _LOGGER.info("Demo: unlock")
        self._locked = False

    async def unlock_trunk(self) -> None:
        _LOGGER.info("Demo: unlock trunk")
        self._tailgate_open = True

    async def honk_flash(self, **kwargs) -> None:
        _LOGGER.info("Demo: honk/flash")

    async def start_climate(self, **kwargs) -> None:
        _LOGGER.info("Demo: start climate with %s", kwargs)
        self._climate_on = True

    async def stop_climate(self) -> None:
        _LOGGER.info("Demo: stop climate")
        self._climate_on = False

    async def start_charging(self) -> int:
        _LOGGER.info("Demo: start charging")
        self._charging = True
        return 0

    async def stop_charging(self) -> int:
        _LOGGER.info("Demo: stop charging")
        self._charging = False
        return 0

    async def start_precleaning(self) -> None:
        _LOGGER.info("Demo: start precleaning")
        self._precleaning_on = True

    async def stop_precleaning(self) -> None:
        _LOGGER.info("Demo: stop precleaning")
        self._precleaning_on = False

    async def set_target_soc(self, level: int, setting_type: ChargeTargetLevelSettingType = ChargeTargetLevelSettingType.DAILY) -> TargetSocResponse:
        _LOGGER.info("Demo: set target SOC to %d (%s)", level, setting_type.name)
        self._target_soc = level
        self._target_soc_setting_type = setting_type
        return await self.get_target_soc()

    async def set_amp_limit(self, amperage: int) -> AmpLimitResponse:
        _LOGGER.info("Demo: set amp limit to %d", amperage)
        self._amp_limit = amperage
        return await self.get_amp_limit()

    async def set_charge_timer(self, timer: BatteryChargeTimer) -> ChargeTimerResponse:
        _LOGGER.info("Demo: set charge timer %s", timer)
        self._charge_timer = timer
        return await self.get_charge_timer()

    async def wakeup(self, **kwargs) -> None:
        _LOGGER.info("Demo: wakeup")

    async def open_windows(self) -> None:
        _LOGGER.info("Demo: open windows")
        self._windows_open = True

    async def close_windows(self) -> None:
        _LOGGER.info("Demo: close windows")
        self._windows_open = False

    async def create_charge_location(
        self,
        alias: str,
        amp_limit: int = 0,
        minimum_soc: int = 0,
        optimised_charging: bool = False,
    ) -> ChargeLocation:
        location = ChargeLocation(
            location_id=f"location-{len(self._charge_locations) + 1}",
            location_alias=alias,
            latitude=59.9139,
            longitude=10.7522,
            amp_limit=amp_limit,
            minimum_soc=minimum_soc,
            is_optimised_charging_enabled=optimised_charging,
            available_optimised_charging=OptimisedChargingType.INTELLIGENT_TIMER,
            location_type=ChargeLocationType.SAVED,
        )
        self._charge_locations.append(location)
        self._current_charge_location_id = location.location_id
        return location

    async def update_charge_location_alias(self, location_id: str, alias: str) -> int:
        self._charge_locations = [
            replace(location, location_alias=alias) if location.location_id == location_id else location
            for location in self._charge_locations
        ]
        return 0

    async def update_charge_location_amp_limit(self, location_id: str, amp_limit: int) -> int:
        self._charge_locations = [
            replace(location, amp_limit=amp_limit) if location.location_id == location_id else location
            for location in self._charge_locations
        ]
        return 0

    async def update_charge_location_min_soc(self, location_id: str, minimum_soc: int) -> int:
        self._charge_locations = [
            replace(location, minimum_soc=minimum_soc) if location.location_id == location_id else location
            for location in self._charge_locations
        ]
        return 0

    async def update_charge_location_optimised(self, location_id: str, enabled: bool) -> int:
        self._charge_locations = [
            replace(location, is_optimised_charging_enabled=enabled) if location.location_id == location_id else location
            for location in self._charge_locations
        ]
        return 0

    async def delete_charge_location(self, location_id: str) -> int:
        self._charge_locations = [location for location in self._charge_locations if location.location_id != location_id]
        if self._current_charge_location_id == location_id:
            self._current_charge_location_id = self._charge_locations[0].location_id if self._charge_locations else None
        return 0

    async def schedule_ota(self, software_id: str, relative_time: int = 0) -> Scheduler:
        self._software_info = replace(self._software_info, state=SoftwareState.INSTALLATION_SCHEDULED)
        self._ota_schedule = replace(
            self._ota_schedule,
            status=ScheduleStatus.SCHEDULED,
            relative_time=relative_time,
            software_id=software_id,
        )
        return self._ota_schedule

    async def install_ota_now(self, software_id: str) -> Scheduler:
        self._software_info = replace(self._software_info, state=SoftwareState.INSTALLATION_STARTED)
        self._ota_schedule = replace(
            self._ota_schedule,
            status=ScheduleStatus.INSTALL,
            software_id=software_id,
        )
        return self._ota_schedule

    async def cancel_ota(self, software_id: str) -> Scheduler:
        self._software_info = replace(self._software_info, state=SoftwareState.INSTALLATION_DEFERRED)
        self._ota_schedule = replace(
            self._ota_schedule,
            status=ScheduleStatus.IDLE,
            software_id=software_id,
            relative_time=0,
        )
        return self._ota_schedule

    async def delete_climate_timer(self, timer_id: str) -> int:
        self._climate_timers = [timer for timer in self._climate_timers if timer.timer_id != timer_id]
        return 0

    async def get_climate_timer_settings(self) -> ParkingClimateTimerSettings:
        return self._climate_timer_settings

    async def set_climate_timer_settings(self, settings: ParkingClimateTimerSettings) -> int:
        _LOGGER.info("Demo: set climate timer settings %s", settings)
        self._climate_timer_settings = settings
        return 1

    def __repr__(self) -> str:
        return f"DemoVehicle(vin={self.vin!r})"
