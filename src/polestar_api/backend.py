"""Backend profiles — gRPC service paths per backend type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendProfile:
    """gRPC service paths for a specific backend.

    Each backend (C3, PCCS, etc.) exposes the same logical services under
    different gRPC package paths.  A BackendProfile maps every service to
    its concrete path so service clients stay backend-agnostic.
    """

    # vehiclestates
    battery_svc: str = "/services.vehiclestates.battery.BatteryService"
    availability_svc: str = "/services.vehiclestates.availability.AvailabilityService"
    climate_svc: str = "/services.vehiclestates.parkingclimatization.ParkingClimatizationService"
    dashboard_svc: str = "/services.vehiclestates.dashboard.DashboardService"
    exterior_svc: str = "/services.vehiclestates.exterior.ExteriorService"
    health_svc: str = "/services.vehiclestates.health.HealthService"
    odometer_svc: str = "/services.vehiclestates.odometer.OdometerService"
    precleaning_svc: str = "/services.vehiclestates.precleaning.PreCleaningService"

    # chronos
    charge_location_svc: str = "/chronos.services.v1.ChargeLocationService"
    charge_now_svc: str = "/chronos.services.v1.ChargeNowService"
    parking_climate_timer_svc: str = "/chronos.services.v1.ParkingClimateTimerService"
    target_soc_svc: str = "/chronos.services.v1.TargetSocService"
    amp_limit_svc: str = "/chronos.services.v1.AmpLimitService"
    charge_timer_svc: str = "/chronos.services.v2.GlobalChargeTimerService"

    # standalone
    invocation_svc: str = "/invocation.InvocationService"
    location_svc: str = "/dtlinternet.DtlInternetService"
    weather_svc: str = "/weather.WeatherService"
    ota_discovery_svc: str = "/ota_mobcache.OtaDiscoveryService"
    ota_scheduler_svc: str = "/ota_mobcache.SchedulerService"


C3 = BackendProfile()

PCCS = BackendProfile(
    battery_svc="/pccs.vehiclestates.services.battery.v1.BatteryService",
    availability_svc="/pccs.vehiclestates.services.availability.v1.AvailabilityService",
    climate_svc="/pccs.vehiclestates.services.parkingclimatization.v1.ParkingClimatizationService",
    dashboard_svc="/pccs.vehiclestates.services.dashboard.v1.DashboardService",
    exterior_svc="/pccs.vehiclestates.services.exterior.v1.ExteriorService",
    health_svc="/pccs.vehiclestates.services.health.v1.HealthService",
    odometer_svc="/pccs.vehiclestates.services.odometer.v1.OdometerService",
    precleaning_svc="/pccs.vehiclestates.services.precleaning.v1.PreCleaningService",
    charge_location_svc="/pccs.chronos.services.v1.ChargeLocationService",
    charge_now_svc="/pccs.chronos.services.v1.ChargeNowService",
    parking_climate_timer_svc="/pccs.chronos.services.v1.ParkingClimateTimerService",
    target_soc_svc="/pccs.chronos.services.v1.TargetSocService",
    amp_limit_svc="/pccs.chronos.services.v1.AmpLimitService",
    charge_timer_svc="/pccs.chronos.services.v2.GlobalChargeTimerService",
    invocation_svc="/pccs.invocation.v1.InvocationService",
    location_svc="/pccs.location.v1.LocationService",
)
