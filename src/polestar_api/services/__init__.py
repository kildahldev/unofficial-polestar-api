"""Service client wrappers grouped by vehicle capability area."""

from .amp_limit import AmpLimitServiceClient
from .availability import AvailabilityServiceClient
from .battery import BatteryServiceClient
from .charge_location import ChargeLocationServiceClient
from .charge_now import ChargeNowServiceClient
from .charge_timer import ChargeTimerServiceClient
from .climate import ClimateServiceClient
from .dashboard import DashboardServiceClient
from .exterior import ExteriorServiceClient
from .health import HealthServiceClient
from .invocation import InvocationServiceClient
from .location import LocationServiceClient
from .odometer import OdometerServiceClient
from .ota import OtaServiceClient
from .parking_climate_timer import ParkingClimateTimerServiceClient
from .precleaning import PreCleaningServiceClient
from .target_soc import TargetSocServiceClient
from .weather import WeatherServiceClient

__all__ = [
    "AmpLimitServiceClient",
    "AvailabilityServiceClient",
    "BatteryServiceClient",
    "ChargeLocationServiceClient",
    "ChargeNowServiceClient",
    "ChargeTimerServiceClient",
    "ClimateServiceClient",
    "DashboardServiceClient",
    "ExteriorServiceClient",
    "HealthServiceClient",
    "InvocationServiceClient",
    "LocationServiceClient",
    "OdometerServiceClient",
    "OtaServiceClient",
    "ParkingClimateTimerServiceClient",
    "PreCleaningServiceClient",
    "TargetSocServiceClient",
    "WeatherServiceClient",
]
