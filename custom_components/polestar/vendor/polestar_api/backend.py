"""Backend profile — gRPC service paths for the Polestar C3 backend.

This library speaks exclusively to C3 (Volvo Cars Cloud Connectivity),
discovered via ``discovery.discover_c3_endpoint()``. The paths below were
observed from the official Android app's C3-flavoured gRPC stubs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackendProfile:
    """gRPC service paths for the C3 backend.

    Every service client takes its service path from here so the concrete
    path strings live in one place.
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
    car_information_svc: str = "/car_information.CarInformation"
    invocation_svc: str = "/invocation.InvocationService"
    location_svc: str = "/dtlinternet.DtlInternetService"
    weather_svc: str = "/weather.WeatherService"
    ota_discovery_svc: str = "/ota_mobcache.OtaDiscoveryService"
    ota_scheduler_svc: str = "/ota_mobcache.SchedulerService"

    # user services (data sharing / privacy consent)
    privacy_settings_svc: str = "/userServices.PrivacySettings"


C3 = BackendProfile()
