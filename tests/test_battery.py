from polestar_api.models.battery import (
    Battery,
    ChargerConnectionStatus,
    ChargerPowerStatus,
    ChargingStatus,
    ChargingType,
    GetBatteryRequest,
    GetBatteryResponse,
)
from polestar_api.models.common import Timestamp


class TestTimestamp:
    def test_round_trip(self):
        ts = Timestamp(seconds=1711900000, nanos=500_000_000)
        data = ts.to_bytes()
        restored = Timestamp.from_bytes(data)
        assert restored.seconds == 1711900000
        assert restored.nanos == 500_000_000

    def test_empty(self):
        ts = Timestamp.from_bytes(b"")
        assert ts.seconds == 0
        assert ts.nanos == 0


class TestBattery:
    def test_round_trip(self):
        battery = Battery(
            charge_level=78.5,
            range_km=312.0,
            range_miles=193.9,
            charging_status=ChargingStatus.CHARGING,
            charger_connection_status=ChargerConnectionStatus.CONNECTED,
            charger_power_status=ChargerPowerStatus.PROVIDING_POWER,
            charging_type=ChargingType.AC,
            power_watts=7400,
            current_amps=32,
            voltage_volts=230,
            time_to_full=120,
        )
        data = battery.to_bytes()
        restored = Battery.from_bytes(data)

        assert restored.charge_level == 78.5
        assert restored.range_km == 312.0
        assert restored.charging_status == ChargingStatus.CHARGING
        assert restored.charger_connection_status == ChargerConnectionStatus.CONNECTED
        assert restored.power_watts == 7400
        assert restored.voltage_volts == 230
        assert restored.time_to_full == 120

    def test_nested_timestamp(self):
        battery = Battery(
            timestamp=Timestamp(seconds=1711900000, nanos=0),
            charge_level=50.0,
        )
        data = battery.to_bytes()
        restored = Battery.from_bytes(data)

        assert restored.timestamp is not None
        assert restored.timestamp.seconds == 1711900000
        assert restored.charge_level == 50.0

    def test_defaults(self):
        battery = Battery()
        assert battery.charge_level == 0.0
        assert battery.charging_status == ChargingStatus.UNSPECIFIED
        assert battery.timestamp is None

    def test_properties(self):
        charging = Battery(charging_status=ChargingStatus.CHARGING)
        assert charging.is_charging

        idle = Battery(charging_status=ChargingStatus.IDLE)
        assert not idle.is_charging

        plugged = Battery(charger_connection_status=ChargerConnectionStatus.CONNECTED)
        assert plugged.is_plugged_in

    def test_all_26_fields_round_trip(self):
        battery = Battery(
            timestamp=Timestamp(seconds=100, nanos=200),
            charge_level=80.0,
            avg_consumption=18.5,
            range_km=300.0,
            time_to_full=90,
            charger_connection_status=ChargerConnectionStatus.CONNECTED,
            charging_status=ChargingStatus.CHARGING,
            range_miles=186.4,
            time_to_target=60,
            power_watts=11000,
            current_amps=48,
            avg_consumption_auto=17.2,
            avg_consumption_since_charge=19.1,
            total_consumption_wh=5000.0,
            total_consumption_wh_auto=4800.0,
            total_consumption_wh_since_charge=200.0,
            charging_type=ChargingType.DC,
            voltage_volts=400,
            time_to_min_soc=15,
            consumption_wh_manual=100.0,
            consumption_wh_auto=95.0,
            consumption_wh_since_charge=5.0,
            consumption_pct_manual=1.2,
            consumption_pct_auto=1.1,
            consumption_pct_since_charge=0.1,
            charger_power_status=ChargerPowerStatus.PROVIDING_POWER,
        )
        data = battery.to_bytes()
        restored = Battery.from_bytes(data)

        assert restored.charge_level == 80.0
        assert restored.charging_type == ChargingType.DC
        assert restored.voltage_volts == 400
        assert restored.charger_power_status == ChargerPowerStatus.PROVIDING_POWER
        assert restored.consumption_pct_since_charge == 0.1
        assert restored.timestamp.seconds == 100


class TestGetBatteryRequest:
    def test_encode(self):
        req = GetBatteryRequest(vin="YV4TEST000T0000001")
        data = req.to_bytes()
        restored = GetBatteryRequest.from_bytes(data)
        assert restored.vin == "YV4TEST000T0000001"


class TestGetBatteryResponse:
    def test_with_nested_battery(self):
        resp = GetBatteryResponse(
            id="123",
            vin="YV4TEST000T0000001",
            battery=Battery(charge_level=95.0, range_km=400.0),
        )
        data = resp.to_bytes()
        restored = GetBatteryResponse.from_bytes(data)

        assert restored.vin == "YV4TEST000T0000001"
        assert restored.battery is not None
        assert restored.battery.charge_level == 95.0
        assert restored.battery.range_km == 400.0
