"""Tests for all domain models — round-trip encode/decode."""

from polestar_api.models.exterior import (
    AlarmStatus,
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
    WindowStatus,
    WindowsStatus,
)
from polestar_api.models.climate import ClimatizationInfo, ClimatizationRunningStatus, ClimatizationRequestType, HeatOrCoolAction
from polestar_api.models.connectivity import ConnectivityInfo, ConnectivityStatus, NetworkType, SignalStrength
from polestar_api.models.dashboard import (
    CarDashboardData,
    CarWarningsData,
    DashboardStatus,
    FluidLevel,
    TyrePressureWarning,
    ServiceWarningTrigger,
)
from polestar_api.models.honkflash import HonkAndFlashRequest, HonkAndFlashResponse, HonkFlashAction
from polestar_api.models.locks import (
    CarLockRequest,
    CarLockResponse,
    CarUnlockRequest,
    CarUnlockResponse,
    LockType,
    UnlockType,
)
from polestar_api.models.availability import Availability, AvailabilityStatus, UnavailableReason, UsageMode
from polestar_api.models.charging import (
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
    TargetSocResponse,
    TimeZoneOffset,
)
from polestar_api.models.charging import DailyTime as ChargeTimerDailyTime
from polestar_api.models.climatization import (
    ClimatizationResponse,
    ClimatizationStartRequest,
    HeatingIntensity,
)
from polestar_api.models.invocation import InvocationResponse, InvocationStatus
from polestar_api.models.health import (
    Health,
    ServiceWarning,
    ExteriorLightWarning,
    TyrePressureWarning as HealthTyrePressureWarning,
    BrakeFluidLevelWarning,
    LowVoltageBatteryWarning,
)
from polestar_api.models.ota import (
    CarSoftwareInfo,
    Scheduler,
    SoftwareDescription,
    SoftwareState,
    ScheduleStatus,
    ScheduleSetBy,
)
from polestar_api.models.weather import WeatherReport
from polestar_api.models.window import WindowControlRequest, WindowControlType
from polestar_api.models.odometer import OdometerStatus
from polestar_api.models.wakeup import WakeUpRequest, WakeUpResponse, WakeUpReason
from polestar_api.models.common import DailyTime, ResponseStatus, Weekday
from polestar_api.models.precleaning import (
    PreCleaningInfo,
    PreCleaningRunningStatus,
    PreCleaningStartReason,
    PreCleaningErrorType,
)
from polestar_api.models.parking_climate_timer import ParkingClimateTimer
from polestar_api.models.charge_location import (
    ChargeLocation,
    ChargeLocationTimer,
    ChargeLocationDepartureTime,
    ChargeLocationType,
    OptimisedChargingType,
)


# -- Exterior --


class TestExteriorStatus:
    def test_defaults(self):
        ext = ExteriorStatus()
        assert ext.is_locked is None
        assert ext.any_door_open is False

    def test_round_trip_nested(self):
        ext = ExteriorStatus(
            central_lock=CentralLockStatus(lock_status=LockStatus.LOCKED),
            doors=DoorsStatus(
                front_left=DoorStatus(open_status=OpenStatus.CLOSED),
                front_right=DoorStatus(open_status=OpenStatus.CLOSED),
                rear_left=DoorStatus(open_status=OpenStatus.OPEN),
                rear_right=DoorStatus(open_status=OpenStatus.CLOSED),
            ),
            windows=WindowsStatus(front_left=WindowStatus(open_status=OpenStatus.CLOSED)),
            sunroof=SunroofStatus(open_status=OpenStatus.CLOSED),
            hood=HoodStatus(status=DoorStatus(open_status=OpenStatus.CLOSED)),
            tailgate=TailgateStatus(status=DoorStatus(open_status=OpenStatus.CLOSED)),
            tank_lid=TankLidStatus(open_status=OpenStatus.CLOSED),
        )
        data = ext.to_bytes()
        restored = ExteriorStatus.from_bytes(data)
        assert restored.central_lock.lock_status == LockStatus.LOCKED
        assert restored.doors.rear_left.open_status == OpenStatus.OPEN
        assert restored.is_locked is True
        assert restored.any_door_open is True

    def test_alarm_status(self):
        door = DoorStatus(
            lock_status=LockStatus.LOCKED,
            alarm_status=AlarmStatus.TRIGGERED,
        )
        data = door.to_bytes()
        restored = DoorStatus.from_bytes(data)
        assert restored.alarm_status == AlarmStatus.TRIGGERED


# -- Climate --


class TestClimatizationInfo:
    def test_defaults(self):
        info = ClimatizationInfo()
        assert info.is_active is False

    def test_round_trip(self):
        info = ClimatizationInfo(
            running_status=ClimatizationRunningStatus.ACTIVE,
            request_type=ClimatizationRequestType.NOW_FROM_REMOTE,
            time_remaining=15,
            heat_or_cool_action=HeatOrCoolAction.HEATING,
        )
        data = info.to_bytes()
        restored = ClimatizationInfo.from_bytes(data)
        assert restored.running_status == ClimatizationRunningStatus.ACTIVE
        assert restored.time_remaining == 15
        assert restored.is_active is True

    def test_temperature_and_seat_fields_are_plain_attributes(self):
        """These are set by ClimateServiceClient._parse_digital_twin, not wire-decoded here."""
        from polestar_api.models.climatization import HeatingIntensity

        info = ClimatizationInfo(
            current_temperature_celsius=21.5,
            target_temperature_celsius=22.0,
            front_left_seat=HeatingIntensity.LEVEL1,
            rear_right_seat=HeatingIntensity.LEVEL3,
            started_at=1_700_000_000,
            ending_at=1_700_000_600,
        )
        assert info.current_temperature_celsius == 21.5
        assert info.rear_right_seat == HeatingIntensity.LEVEL3
        assert info.ending_at == 1_700_000_600


# -- Connectivity --


class TestConnectivityInfo:
    def test_defaults(self):
        info = ConnectivityInfo()
        assert info.is_connected is False

    def test_round_trip(self):
        info = ConnectivityInfo(
            status=ConnectivityStatus.CONNECTED,
            network_type=NetworkType.LTE,
            signal_strength=SignalStrength.STRONG,
        )
        data = info.to_bytes()
        restored = ConnectivityInfo.from_bytes(data)
        assert restored.status == ConnectivityStatus.CONNECTED
        assert restored.network_type == NetworkType.LTE
        assert restored.signal_strength == SignalStrength.STRONG
        assert restored.is_connected is True


# -- Dashboard --


class TestDashboardStatus:
    def test_defaults(self):
        ds = DashboardStatus()
        assert ds.dashboard_data is None
        assert ds.warnings_data is None

    def test_round_trip(self):
        ds = DashboardStatus(
            dashboard_data=CarDashboardData(
                odometer_km=12345.6,
                trip_meter_manual_km=100.5,
                trip_meter_auto_km=200.3,
                distance_to_empty=350,
                fuel_amount_litres=0.0,
            ),
            warnings_data=CarWarningsData(
                tyre_front_left=TyrePressureWarning.NO_WARNING,
                tyre_front_right=TyrePressureWarning.NO_WARNING,
                tyre_rear_left=TyrePressureWarning.SOFT_WARNING,
                tyre_rear_right=TyrePressureWarning.NO_WARNING,
                brake_fluid=FluidLevel.HIGH,
                service_warning_trigger=ServiceWarningTrigger.NO_REMINDER,
            ),
        )
        data = ds.to_bytes()
        restored = DashboardStatus.from_bytes(data)
        assert restored.dashboard_data.odometer_km == 12345.6
        assert restored.dashboard_data.distance_to_empty == 350
        assert restored.warnings_data.tyre_rear_left == TyrePressureWarning.SOFT_WARNING
        assert restored.warnings_data.brake_fluid == FluidLevel.HIGH


# -- Honk / Flash --


class TestHonkAndFlash:
    def test_request_round_trip(self):
        req = HonkAndFlashRequest(honk_flash_type=HonkFlashAction.HONK_AND_FLASH)
        data = req.to_bytes()
        restored = HonkAndFlashRequest.from_bytes(data)
        assert restored.honk_flash_type == HonkFlashAction.HONK_AND_FLASH

    def test_response_round_trip(self):
        resp = HonkAndFlashResponse(
            response=InvocationResponse(
                vin="YV4H60AB1R1000001",
                status=InvocationStatus.SUCCESS,
            ),
        )
        data = resp.to_bytes()
        restored = HonkAndFlashResponse.from_bytes(data)
        assert restored.response.status == InvocationStatus.SUCCESS


# -- Locks --


class TestLocks:
    def test_lock_request_round_trip(self):
        req = CarLockRequest(lock_type=LockType.LOCK)
        data = req.to_bytes()
        restored = CarLockRequest.from_bytes(data)
        assert restored.lock_type == LockType.LOCK

    def test_lock_reduced_guard(self):
        req = CarLockRequest(lock_type=LockType.LOCK_REDUCED_GUARD)
        data = req.to_bytes()
        restored = CarLockRequest.from_bytes(data)
        assert restored.lock_type == LockType.LOCK_REDUCED_GUARD

    def test_unlock_request_round_trip(self):
        req = CarUnlockRequest(unlock_type=UnlockType.UNLOCK_TYPE_UNSPECIFIED)
        data = req.to_bytes()
        restored = CarUnlockRequest.from_bytes(data)
        assert restored.unlock_type == UnlockType.UNLOCK_TYPE_UNSPECIFIED

    def test_trunk_unlock_request(self):
        req = CarUnlockRequest(unlock_type=UnlockType.UNLOCK_TYPE_TRUNK_ONLY)
        data = req.to_bytes()
        restored = CarUnlockRequest.from_bytes(data)
        assert restored.unlock_type == UnlockType.UNLOCK_TYPE_TRUNK_ONLY


# -- Odometer --


class TestOdometerStatus:
    def test_defaults(self):
        odo = OdometerStatus()
        assert odo.odometer_km == 0.0

    def test_round_trip(self):
        odo = OdometerStatus(odometer_meters=54321000)
        data = odo.to_bytes()
        restored = OdometerStatus.from_bytes(data)
        assert restored.odometer_meters == 54321000
        assert restored.odometer_km == 54321.0


# -- WakeUp --


class TestWakeUp:
    def test_request_default(self):
        req = WakeUpRequest()
        data = req.to_bytes()
        restored = WakeUpRequest.from_bytes(data)
        assert restored.reason == WakeUpReason.UNDEFINED

    def test_request_with_reason(self):
        req = WakeUpRequest(reason=WakeUpReason.OTA_DOWNLOAD)
        data = req.to_bytes()
        restored = WakeUpRequest.from_bytes(data)
        assert restored.reason == WakeUpReason.OTA_DOWNLOAD

    def test_response_round_trip(self):
        resp = WakeUpResponse(
            response_status=ResponseStatus(status_code=0),
        )
        data = resp.to_bytes()
        restored = WakeUpResponse.from_bytes(data)
        assert restored.response_status.status_code == 0


# -- Charging --


class TestTargetSoc:
    def test_set_request_round_trip(self):
        req = SetTargetSocRequest(
            target_level=80,
            setting_type=ChargeTargetLevelSettingType.DAILY,
        )
        data = req.to_bytes()
        restored = SetTargetSocRequest.from_bytes(data)
        assert restored.target_level == 80
        assert restored.setting_type == ChargeTargetLevelSettingType.DAILY

    def test_response_round_trip(self):
        resp = TargetSocResponse(
            response_status=ResponseStatus(status_code=0),
            target_level=80,
        )
        data = resp.to_bytes()
        restored = TargetSocResponse.from_bytes(data)
        assert restored.target_level == 80


class TestAmpLimit:
    def test_set_request_round_trip(self):
        req = SetAmpLimitRequest(amperage_limit=16)
        data = req.to_bytes()
        restored = SetAmpLimitRequest.from_bytes(data)
        assert restored.amperage_limit == 16

    def test_response_round_trip(self):
        resp = AmpLimitResponse(
            response_status=ResponseStatus(status_code=0),
            amperage_limit=16,
        )
        data = resp.to_bytes()
        restored = AmpLimitResponse.from_bytes(data)
        assert restored.amperage_limit == 16


class TestChargeTimer:
    def test_timer_round_trip(self):
        timer = BatteryChargeTimer(
            start=ChargeTimerDailyTime(
                hour=20, minute=0, time_zone=TimeZoneOffset(offset_minutes=60),
            ),
            stop=ChargeTimerDailyTime(
                hour=6, minute=30, time_zone=TimeZoneOffset(offset_minutes=60),
            ),
            activated=True,
        )
        data = timer.to_bytes()
        restored = BatteryChargeTimer.from_bytes(data)
        assert restored.start.hour == 20
        assert restored.start.minute == 0
        assert restored.start.time_zone.offset_minutes == 60
        assert restored.stop.hour == 6
        assert restored.stop.minute == 30
        assert restored.activated is True

    def test_set_request_nested(self):
        timer = BatteryChargeTimer(
            start=ChargeTimerDailyTime(hour=10, minute=0),
            stop=ChargeTimerDailyTime(hour=20, minute=0),
            activated=True,
        )
        req = SetChargeTimerRequest(timer=timer)
        data = req.to_bytes()
        restored = SetChargeTimerRequest.from_bytes(data)
        assert restored.timer.start.hour == 10
        assert restored.timer.activated is True

    def test_response_nested(self):
        timer = BatteryChargeTimer(
            start=ChargeTimerDailyTime(hour=10, minute=0),
            stop=ChargeTimerDailyTime(hour=20, minute=0),
            activated=False,
        )
        resp = ChargeTimerResponse(
            response_status=ResponseStatus(status_code=0),
            timer=timer,
        )
        data = resp.to_bytes()
        restored = ChargeTimerResponse.from_bytes(data)
        assert restored.timer.stop.hour == 20
        assert restored.timer.stop.minute == 0


class TestChargeNow:
    def test_request_round_trip(self):
        req = ChargeNowRequest(charge_now=True)
        data = req.to_bytes()
        restored = ChargeNowRequest.from_bytes(data)
        assert restored.charge_now is True


class TestStopResumeCharging:
    def test_request_round_trip(self):
        req = StopResumeChargingRequest(command=StopResumeChargingCommand.STOP_CHARGING)
        data = req.to_bytes()
        restored = StopResumeChargingRequest.from_bytes(data)
        assert restored.command == StopResumeChargingCommand.STOP_CHARGING


# -- Health --


class TestHealth:
    def test_defaults(self):
        h = Health()
        assert h.any_tyre_warning is False

    def test_round_trip(self):
        h = Health(
            days_to_service=45,
            distance_to_service_km=5000,
            service_warning=ServiceWarning.NO_WARNING,
            brake_fluid_level_warning=BrakeFluidLevelWarning.NO_WARNING,
            front_left_tyre_pressure_warning=HealthTyrePressureWarning.LOW_PRESSURE,
            front_left_tyre_pressure_kpa=210.5,
            low_voltage_battery_warning=LowVoltageBatteryWarning.NO_WARNING,
            brake_light_left_warning=ExteriorLightWarning.NO_WARNING,
        )
        data = h.to_bytes()
        restored = Health.from_bytes(data)
        assert restored.days_to_service == 45
        assert restored.distance_to_service_km == 5000
        assert restored.front_left_tyre_pressure_warning == HealthTyrePressureWarning.LOW_PRESSURE
        assert restored.front_left_tyre_pressure_kpa == 210.5
        assert restored.any_tyre_warning is True


# -- Availability --


class TestAvailability:
    def test_defaults(self):
        a = Availability()
        assert a.is_available is False

    def test_round_trip(self):
        a = Availability(
            availability_status=AvailabilityStatus.AVAILABLE,
            usage_mode=UsageMode.INACTIVE,
        )
        data = a.to_bytes()
        restored = Availability.from_bytes(data)
        assert restored.is_available is True
        assert restored.usage_mode == UsageMode.INACTIVE

    def test_unavailable_with_reason(self):
        a = Availability(
            availability_status=AvailabilityStatus.UNAVAILABLE,
            unavailable_reason=UnavailableReason.POWER_SAVING_MODE,
        )
        data = a.to_bytes()
        restored = Availability.from_bytes(data)
        assert restored.is_available is False
        assert restored.unavailable_reason == UnavailableReason.POWER_SAVING_MODE


# -- Window Control --


class TestWindowControl:
    def test_open_round_trip(self):
        req = WindowControlRequest(windows_control=WindowControlType.OPEN_ALL)
        data = req.to_bytes()
        restored = WindowControlRequest.from_bytes(data)
        assert restored.windows_control == WindowControlType.OPEN_ALL

    def test_close_round_trip(self):
        req = WindowControlRequest(windows_control=WindowControlType.CLOSE_ALL)
        data = req.to_bytes()
        restored = WindowControlRequest.from_bytes(data)
        assert restored.windows_control == WindowControlType.CLOSE_ALL


# -- Climatization Start/Stop --


class TestClimatizationStartStop:
    def test_start_request(self):
        req = ClimatizationStartRequest(
            compartment_temperature_celsius=22.0,
            front_left_seat=HeatingIntensity.LEVEL2,
            steering_wheel=HeatingIntensity.LEVEL1,
        )
        data = req.to_bytes()
        restored = ClimatizationStartRequest.from_bytes(data)
        assert restored.compartment_temperature_celsius == 22.0
        assert restored.front_left_seat == HeatingIntensity.LEVEL2
        assert restored.steering_wheel == HeatingIntensity.LEVEL1

    def test_response(self):
        resp = ClimatizationResponse(
            response=InvocationResponse(
                vin="YV4H60AB1R1000001",
                status=InvocationStatus.SUCCESS,
            ),
        )
        data = resp.to_bytes()
        restored = ClimatizationResponse.from_bytes(data)
        assert restored.response.status == InvocationStatus.SUCCESS
        assert restored.response.vin == "YV4H60AB1R1000001"


# -- Weather --


class TestWeatherReport:
    def test_round_trip(self):
        w = WeatherReport(
            timestamp_epoch_millis=1711929600000,
            temperature_celsius=18.5,
        )
        data = w.to_bytes()
        restored = WeatherReport.from_bytes(data)
        assert restored.timestamp_epoch_millis == 1711929600000
        assert restored.temperature_celsius == 18.5


# -- OTA --


class TestOta:
    def test_software_info_round_trip(self):
        info = CarSoftwareInfo(
            software_id="SW-12345",
            description=SoftwareDescription(
                name="System Update 2.3",
                short_desc="Bug fixes",
            ),
            state=SoftwareState.DOWNLOAD_READY,
            new_sw_version="2.3.0",
        )
        data = info.to_bytes()
        restored = CarSoftwareInfo.from_bytes(data)
        assert restored.software_id == "SW-12345"
        assert restored.description.name == "System Update 2.3"
        assert restored.state == SoftwareState.DOWNLOAD_READY
        assert restored.new_sw_version == "2.3.0"

    def test_scheduler_round_trip(self):
        sched = Scheduler(
            status=ScheduleStatus.SCHEDULED,
            relative_time=3600,
            software_id="SW-12345",
            set_by=ScheduleSetBy.APP,
        )
        data = sched.to_bytes()
        restored = Scheduler.from_bytes(data)
        assert restored.status == ScheduleStatus.SCHEDULED
        assert restored.relative_time == 3600
        assert restored.set_by == ScheduleSetBy.APP


# -- Pre-cleaning --


class TestPreCleaning:
    def test_defaults(self):
        info = PreCleaningInfo()
        assert info.is_running is False
        assert info.running_status == PreCleaningRunningStatus.UNSPECIFIED

    def test_round_trip(self):
        info = PreCleaningInfo(
            running_status=PreCleaningRunningStatus.ON,
            start_reason=PreCleaningStartReason.REMOTE,
            runtime_left_minutes=25,
            measured_air_quality_index=42,
            measured_particulate_matter_2_5=15,
        )
        data = info.to_bytes()
        restored = PreCleaningInfo.from_bytes(data)
        assert restored.is_running is True
        assert restored.start_reason == PreCleaningStartReason.REMOTE
        assert restored.runtime_left_minutes == 25
        assert restored.measured_air_quality_index == 42
        assert restored.measured_particulate_matter_2_5 == 15

    def test_error_round_trip(self):
        info = PreCleaningInfo(
            running_status=PreCleaningRunningStatus.OFF,
            error=PreCleaningErrorType.INTERRUPTED,
        )
        data = info.to_bytes()
        restored = PreCleaningInfo.from_bytes(data)
        assert restored.error == PreCleaningErrorType.INTERRUPTED


# -- DailyTime --


class TestDailyTime:
    def test_round_trip(self):
        t = DailyTime(hour=7, minute=30)
        data = t.to_bytes()
        restored = DailyTime.from_bytes(data)
        assert restored.hour == 7
        assert restored.minute == 30


# -- Parking Climate Timer --


class TestParkingClimateTimer:
    def test_construction(self):
        timer = ParkingClimateTimer(
            timer_id="abc-123",
            index=0,
            ready_at_hour=7,
            ready_at_minute=0,
            activated=True,
            repeat=True,
            weekdays=(Weekday.MONDAY, Weekday.FRIDAY),
        )
        assert timer.timer_id == "abc-123"
        assert timer.activated is True
        assert Weekday.MONDAY in timer.weekdays
        assert Weekday.FRIDAY in timer.weekdays


# -- Charge Location --


class TestChargeLocation:
    def test_construction(self):
        loc = ChargeLocation(
            location_id="loc-001",
            location_alias="Home",
            latitude=59.3293,
            longitude=18.0686,
            amp_limit=16,
            minimum_soc=20,
            location_type=ChargeLocationType.SAVED,
            available_optimised_charging=OptimisedChargingType.INTELLIGENT_TIMER,
        )
        assert loc.location_alias == "Home"
        assert loc.amp_limit == 16
        assert loc.location_type == ChargeLocationType.SAVED

    def test_with_timers(self):
        timer = ChargeLocationTimer(
            id="t-1",
            activated=True,
            start_hour=22, start_minute=0,
            stop_hour=6, stop_minute=0,
            active_days=(Weekday.MONDAY, Weekday.TUESDAY),
        )
        departure = ChargeLocationDepartureTime(
            id="d-1",
            activated=True,
            hour=7, minute=30,
            active_days=(Weekday.WEDNESDAY,),
        )
        loc = ChargeLocation(
            location_id="loc-002",
            charge_timers=(timer,),
            departure_times=(departure,),
        )
        assert len(loc.charge_timers) == 1
        assert loc.charge_timers[0].start_hour == 22
        assert len(loc.departure_times) == 1
        assert loc.departure_times[0].hour == 7


# -- Packed Varints --


class TestPackedVarints:
    def test_decode_packed_varints(self):
        from polestar_api.codec import decode_packed_varints, encode_packed_varints
        values = [1, 3, 5, 7]
        encoded = encode_packed_varints(6, values)
        # Strip the tag + length prefix to get just the packed data
        from polestar_api.codec import decode_varint
        _, pos = decode_varint(encoded, 0)  # skip tag
        length, pos = decode_varint(encoded, pos)  # skip length
        packed_data = encoded[pos:pos + length]
        result = decode_packed_varints(packed_data)
        assert result == values


def test_health_decodes_tyre_status_and_reference_pressures():
    from polestar_api.models.health import Health, TpmsSensorMeasurement, TpmsStatus, TyrePressureValueStatus, TyreStatus
    from polestar_api.models.common import Timestamp

    status = TyreStatus(
        front_left_value_status=TyrePressureValueStatus.OK,
        front_right_value_status=TyrePressureValueStatus.OK,
        rear_left_value_status=TyrePressureValueStatus.UNVERIFIED,
        rear_right_value_status=TyrePressureValueStatus.OK,
        value_status_updated_at=Timestamp(seconds=1700000000),
        sensor_measurement=TpmsSensorMeasurement.DIRECT,
        system_status=TpmsStatus.OK,
    )
    health = Health(
        front_left_tyre_pressure_kpa=250.0,
        front_tyres_reference_pressure_kpa=260.0,
        rear_tyres_reference_pressure_kpa=270.0,
        tyre_status=status,
    )
    decoded = Health.from_bytes(health.to_bytes())
    assert decoded.front_tyres_reference_pressure_kpa == 260.0
    assert decoded.rear_tyres_reference_pressure_kpa == 270.0
    assert decoded.tyre_status.system_status is TpmsStatus.OK
    assert decoded.tyre_status.sensor_measurement is TpmsSensorMeasurement.DIRECT
    assert decoded.tyre_status.rear_left_value_status is TyrePressureValueStatus.UNVERIFIED
    assert decoded.tyre_status.value_status_updated_at.seconds == 1700000000
    assert decoded.tyre_status.all_values_ok is False


def test_health_tyre_wire_order_matches_physical_wheels():
    """Fields 39-42 are FR, RR, FL, RL (verified with distinct per-wheel pressures).

    Credit: this ordering was empirically verified by Hugo Venter
    (hugo-nz/unofficial-polestar-api) by setting each tyre to a distinct
    pressure and matching the raw kPa fields against physical gauge
    readings. See https://github.com/hugo-nz/unofficial-polestar-api.
    """
    import struct

    from polestar_api.models.health import Health

    def f32(field, value):
        key, out = (field << 3) | 5, b""
        while key > 0x7F:
            out += bytes([(key & 0x7F) | 0x80])
            key >>= 7
        return out + bytes([key]) + struct.pack("<f", value)

    raw = f32(39, 272.5) + f32(40, 282.5) + f32(41, 260.0) + f32(42, 245.0)
    h = Health.from_bytes(raw)
    assert h.front_right_tyre_pressure_kpa == 272.5
    assert h.rear_right_tyre_pressure_kpa == 282.5
    assert h.front_left_tyre_pressure_kpa == 260.0
    assert h.rear_left_tyre_pressure_kpa == 245.0
