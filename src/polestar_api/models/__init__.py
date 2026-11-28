"""Typed protobuf-backed models exposed by the Polestar API client."""

from .availability import Availability, AvailabilityStatus, UnavailableReason, UsageMode
from .battery import Battery, GetBatteryResponse
from .charging import (
    AmpLimitResponse,
    BatteryChargeTimer,
    ChargeNowRequest,
    ChargeNowResponse,
    ChargeTargetLevelSettingType,
    ChargeTimerResponse,
    SetAmpLimitRequest,
    SetChargeTimerRequest,
    SetTargetSocRequest,
    StopResumeChargingCommand,
    StopResumeChargingRequest,
    StopResumeChargingResponse,
    TargetSocResponse,
)
from .climate import ClimatizationInfo
from .climatization import ClimatizationResponse, ClimatizationStartRequest, HeatingIntensity
from .charge_location import (
    ChargeLocation,
    ChargeLocationDepartureTime,
    ChargeLocationTimer,
    ChargeLocationType,
    OptimisedChargingType,
)
from .common import Coordinate, DailyTime, Location, ResponseStatus, Timestamp, VehicleRequest, Weekday
from .connectivity import ConnectivityInfo, ConnectivityStatus, NetworkType, SignalStrength
from .dashboard import CarDashboardData, CarWarningsData, DashboardStatus
from .errors import CommandError
from .exterior import ExteriorStatus
from .health import Health
from .honkflash import HonkAndFlashRequest, HonkAndFlashResponse
from .invocation import InvocationRequest, InvocationResponse, InvocationStatus
from .location import LocationRequest, LocationResponse, LocationStatusUpdate
from .locks import CarLockRequest, CarLockResponse, CarUnlockRequest, CarUnlockResponse
from .mycars import CarPreview
from .odometer import OdometerStatus
from .ota import CarSoftwareInfo, Scheduler, SoftwareDescription, SoftwareState, ScheduleStatus
from .parking_climate_timer import ParkingClimateTimer
from .privacy import PrivacySetting, PrivacySettingType
from .precleaning import PreCleaningErrorType, PreCleaningInfo, PreCleaningRunningStatus, PreCleaningStartReason
from .wakeup import WakeUpRequest, WakeUpResponse, WakeUpReason
from .weather import WeatherReport
from .window import WindowControlRequest, WindowControlType

__all__ = [
    "AmpLimitResponse",
    "Availability",
    "AvailabilityStatus",
    "Battery",
    "BatteryChargeTimer",
    "CarDashboardData",
    "CarPreview",
    "CommandError",
    "ChargeLocation",
    "ChargeLocationDepartureTime",
    "ChargeLocationTimer",
    "CarLockRequest",
    "CarLockResponse",
    "CarUnlockRequest",
    "CarUnlockResponse",
    "CarWarningsData",
    "ChargeNowRequest",
    "ChargeNowResponse",
    "ChargeTargetLevelSettingType",
    "ChargeTimerResponse",
    "ClimatizationInfo",
    "ClimatizationResponse",
    "ClimatizationStartRequest",
    "ConnectivityInfo",
    "ConnectivityStatus",
    "Coordinate",
    "DailyTime",
    "DashboardStatus",
    "ExteriorStatus",
    "Health",
    "HeatingIntensity",
    "VehicleRequest",
    "GetBatteryResponse",
    "HonkAndFlashRequest",
    "HonkAndFlashResponse",
    "InvocationRequest",
    "InvocationResponse",
    "InvocationStatus",
    "Location",
    "ChargeLocationType",
    "LocationRequest",
    "LocationResponse",
    "LocationStatusUpdate",
    "NetworkType",
    "OdometerStatus",
    "OptimisedChargingType",
    "ParkingClimateTimer",
    "PreCleaningErrorType",
    "PrivacySetting",
    "PrivacySettingType",
    "PreCleaningInfo",
    "PreCleaningRunningStatus",
    "PreCleaningStartReason",
    "ResponseStatus",
    "SetAmpLimitRequest",
    "SetChargeTimerRequest",
    "SetTargetSocRequest",
    "SignalStrength",
    "StopResumeChargingCommand",
    "StopResumeChargingRequest",
    "StopResumeChargingResponse",
    "TargetSocResponse",
    "Timestamp",
    "WakeUpReason",
    "CarSoftwareInfo",
    "Scheduler",
    "ScheduleStatus",
    "SoftwareDescription",
    "SoftwareState",
    "UnavailableReason",
    "UsageMode",
    "Weekday",
    "WakeUpRequest",
    "WakeUpResponse",
    "WeatherReport",
    "WindowControlRequest",
    "WindowControlType",
]
