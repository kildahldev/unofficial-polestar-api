"""Live integration tests for Polestar API.

These tests connect to the real Polestar APIs using credentials from
environment variables or a `.env` file. They are skipped if credentials
are not provided.

Usage:
    # Create a .env file first (see .env.example):
    #   POLESTAR_EMAIL=your_email@example.com
    #   POLESTAR_PASSWORD=your_password
    
    # Run live tests (automatically loads .env)
    pytest tests/test_live_integration.py -v -m live

    # Or override with environment variables
    POLESTAR_EMAIL=... POLESTAR_PASSWORD=... pytest tests/test_live_integration.py -v -m live

    # Run specific test
    pytest tests/test_live_integration.py::TestLiveBattery::test_get_battery -v
"""

import os
import ssl
from pathlib import Path

import certifi
import pytest

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

from polestar_api import PolestarApi
from polestar_api.exceptions import AuthError
from polestar_api.models.climate import ClimatizationRunningStatus


# Load .env file before any tests run
if HAS_DOTENV:
    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)


@pytest.fixture(autouse=True)
def configure_ssl():
    """Fix SSL CA certificate verification on macOS Python 3.14+.

    Python 3.14 on macOS doesn't find system CA certificates, causing
    SSL verification to fail. Load certifi's CA bundle into the pre-built
    SSL contexts in auth.py, discovery.py, and connection.py (all created
    at import time before this fixture runs).

    Uses separate contexts for HTTP/1.1 (httpx) and HTTP/2 (grpclib)
    because httpx overwrites the ALPN setting on its context.
    """
    http_ctx = ssl.create_default_context(cafile=certifi.where())
    grpc_ctx = ssl.create_default_context(cafile=certifi.where())
    grpc_ctx.set_alpn_protocols(["h2"])

    from polestar_api import auth, connection, discovery
    auth._HTTPX_SSL_CONTEXT = http_ctx
    discovery._SSL_CONTEXT = http_ctx
    connection._SSL_CONTEXT = grpc_ctx


@pytest.fixture
def has_live_credentials():
    """Check if live test credentials are available."""
    email = os.environ.get("POLESTAR_EMAIL")
    password = os.environ.get("POLESTAR_PASSWORD")
    return bool(email and password)


@pytest.fixture
def live_credentials():
    """Get live credentials from environment."""
    email = os.environ.get("POLESTAR_EMAIL")
    password = os.environ.get("POLESTAR_PASSWORD")
    if not email or not password:
        pytest.skip("POLESTAR_EMAIL and POLESTAR_PASSWORD environment variables required")
    return email, password


@pytest.fixture
async def api_client(live_credentials):
    """Create an authenticated API client."""
    email, password = live_credentials
    api = PolestarApi(email=email, password=password)
    await api.async_init()
    yield api
    await api.close()


@pytest.fixture
async def vehicle(api_client):
    """Get the first vehicle from the account."""
    vehicles = await api_client.get_vehicles()
    if not vehicles:
        pytest.skip("No vehicles found on account")
    return vehicles[0]


class TestLiveAuth:
    """Test authentication with real credentials."""

    @pytest.mark.live
    def test_credentials_provided(self, has_live_credentials):
        """Verify credentials are available (or skip test)."""
        if not has_live_credentials:
            pytest.skip("Set POLESTAR_EMAIL and POLESTAR_PASSWORD to run live tests")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_auth_succeeds(self, live_credentials):
        """Test that authentication works with provided credentials."""
        email, password = live_credentials
        api = PolestarApi(email=email, password=password)
        try:
            await api.async_init()
            assert api._auth.access_token is not None
            assert len(api._auth.access_token) > 0
        finally:
            await api.close()

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_auth_invalid_credentials(self):
        """Test that invalid credentials raise AuthError."""
        api = PolestarApi(email="invalid@example.com", password="wrongpassword")
        with pytest.raises(AuthError):
            await api.async_init()
        await api.close()


class TestLiveVehicleDiscovery:
    """Test vehicle discovery with real account."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_vehicles(self, api_client):
        """Test fetching vehicle list."""
        vehicles = await api_client.get_vehicles()
        assert isinstance(vehicles, list)
        assert len(vehicles) > 0
        for v in vehicles:
            print(f"  Vehicle: {v.model_name} ({v.model_year}) VIN={v.vin}")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_vehicle_has_vin(self, vehicle):
        """Test that vehicle has valid VIN."""
        assert vehicle.vin is not None
        assert len(vehicle.vin) == 17
        print(f"  VIN: {vehicle.vin}")


class TestLiveBattery:
    """Test battery API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_battery(self, vehicle):
        """Test getting battery status."""
        battery = await vehicle.get_battery()
        if battery is not None:
            assert 0 <= battery.charge_level <= 100
            assert battery.range_km >= 0
            print(f"  Battery: {battery.charge_level}% charge, {battery.range_km:.1f} km range")
            print(f"  Status: {battery.charging_status.name}, plugged={battery.is_plugged_in}")
            if battery.is_charging:
                print(f"  Charging: {battery.power_watts}W, {battery.voltage_volts}V")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_battery_properties(self, vehicle):
        """Test battery status properties."""
        battery = await vehicle.get_battery()
        if battery is not None:
            assert isinstance(battery.is_charging, bool)
            assert isinstance(battery.is_plugged_in, bool)
            print(f"  is_charging={battery.is_charging}, is_plugged_in={battery.is_plugged_in}")


class TestLiveLocation:
    """Test location API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_location(self, vehicle):
        """Test getting last known location."""
        location = await vehicle.get_location()
        if location is not None and location.coordinate is not None:
            assert -90 <= location.coordinate.latitude <= 90
            assert -180 <= location.coordinate.longitude <= 180
            print(f"  Location: {location.coordinate.latitude:.6f}, {location.coordinate.longitude:.6f}")
            print(f"  Altitude: {location.altitude}m, Heading: {location.heading}°, Speed: {location.speed}")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_parked_location(self, vehicle):
        """Test getting parked location."""
        parked = await vehicle.get_parked_location()
        if parked is not None and parked.coordinate is not None:
            assert -90 <= parked.coordinate.latitude <= 90
            assert -180 <= parked.coordinate.longitude <= 180
            print(f"  Parked: {parked.coordinate.latitude:.6f}, {parked.coordinate.longitude:.6f}")


class TestLiveExterior:
    """Test exterior status endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_exterior(self, vehicle):
        """Test getting exterior status."""
        exterior = await vehicle.get_exterior()
        if exterior is not None:
            assert isinstance(exterior.is_locked, bool)
            assert isinstance(exterior.any_door_open, bool)
            print(f"  Locked: {exterior.is_locked}, any_door_open: {exterior.any_door_open}")
            if exterior.doors:
                print(f"  Doors: {exterior.doors}")
            if exterior.windows:
                print(f"  Windows: {exterior.windows}")


class TestLiveClimate:
    """Test climate API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_climate(self, vehicle):
        """Test getting climate status."""
        climate = await vehicle.get_climate()
        if climate is not None:
            assert isinstance(climate.is_active, bool)
            assert isinstance(climate.running_status, ClimatizationRunningStatus)
            print(f"  Running: {climate.running_status.name}, active: {climate.is_active}")
            print(f"  Request type: {climate.request_type.name}")
            print(f"  Time remaining: {climate.time_remaining}s")
            print(f"  Action: {climate.heat_or_cool_action.name}")
            if climate.current_temperature_celsius is not None:
                print(f"  Current temp: {climate.current_temperature_celsius}°C")
            if climate.target_temperature_celsius is not None:
                print(f"  Target temp: {climate.target_temperature_celsius}°C")


class TestLiveOdometer:
    """Test odometer API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_odometer(self, vehicle):
        """Test getting odometer reading."""
        odometer = await vehicle.get_odometer()
        if odometer is not None:
            assert odometer.odometer_km >= 0
            print(f"  Odometer: {odometer.odometer_km:.1f} km")
            print(f"  Trip manual: {odometer.trip_meter_manual_km:.1f} km")
            print(f"  Trip automatic: {odometer.trip_meter_automatic_km:.1f} km")


class TestLiveHealth:
    """Test health API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_health(self, vehicle):
        """Test getting health status."""
        health = await vehicle.get_health()
        if health is not None:
            print(f"  Health: {health}")


class TestLiveAvailability:
    """Test availability API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_availability(self, vehicle):
        """Test getting availability status."""
        availability = await vehicle.get_availability()
        if availability is not None:
            assert isinstance(availability.is_available, bool)
            print(f"  Available: {availability.is_available}")
            if hasattr(availability, "unavailable_reason"):
                print(f"  Reason: {availability.unavailable_reason}")


class TestLiveWeather:
    """Test weather API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_weather(self, vehicle):
        """Test getting weather report."""
        weather = await vehicle.get_weather()
        if weather is not None:
            assert weather.temperature_celsius is not None
            print(f"  Weather: {weather}")


class TestLiveCharging:
    """Test charging API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_target_soc(self, vehicle):
        """Test getting target SOC."""
        target_soc = await vehicle.get_target_soc()
        assert 0 <= target_soc.target_level <= 100
        print(f"  Target SOC: {target_soc.target_level}%")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_amp_limit(self, vehicle):
        """Test getting amp limit. Not supported on Polestar 4."""
        from grpclib.exceptions import GRPCError
        from grpclib.const import Status
        try:
            amp_limit = await vehicle.get_amp_limit()
            assert amp_limit.amp_limit >= 0
            print(f"  Amp limit: {amp_limit.amp_limit}A")
        except GRPCError as e:
            assert e.status == Status.UNIMPLEMENTED
            print(f"  Amp limit: UNIMPLEMENTED ({e.message})")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_charge_timer(self, vehicle):
        """Test getting charge timer."""
        charge_timer = await vehicle.get_charge_timer()
        assert charge_timer is not None
        print(f"  Charge timer: {charge_timer}")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_charge_locations(self, vehicle):
        """Test getting charge locations."""
        locations = await vehicle.get_charge_locations()
        assert isinstance(locations, list)
        print(f"  Charge locations: {len(locations)} saved")
        for loc in locations:
            print(f"    - {loc}")


class TestLivePreCleaning:
    """Test pre-cleaning API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_precleaning(self, vehicle):
        """Test getting pre-cleaning status."""
        precleaning = await vehicle.get_precleaning()
        if precleaning is not None:
            assert isinstance(precleaning.is_running, bool)
            print(f"  Pre-cleaning: running={precleaning.is_running}")
            print(f"  Details: {precleaning}")
        else:
            print(f"  Pre-cleaning: unavailable (None)")


class TestLiveOTA:
    """Test OTA API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_software_info(self, vehicle):
        """Test getting software info."""
        ota_info = await vehicle.get_software_info()
        if ota_info is not None:
            print(f"  Software: {ota_info}")
        else:
            print(f"  Software: unavailable (None)")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_ota_schedule(self, vehicle):
        """Test getting OTA schedule."""
        schedule = await vehicle.get_ota_schedule()
        if schedule is not None:
            print(f"  Schedule: {schedule}")
        else:
            print(f"  Schedule: unavailable (None)")


class TestLiveDashboard:
    """Test dashboard API endpoints (legacy PCCS)."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_dashboard(self, vehicle):
        """Test getting dashboard status. UNIMPLEMENTED on Digital Twin (P4)."""
        from grpclib.exceptions import GRPCError
        from grpclib.const import Status
        try:
            dashboard = await vehicle.get_dashboard()
            print(f"  Dashboard: {dashboard}")
        except GRPCError as e:
            assert e.status == Status.UNIMPLEMENTED
            print(f"  Dashboard: UNIMPLEMENTED ({e.message})")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_connectivity(self, vehicle):
        """Test getting connectivity status. UNIMPLEMENTED on Digital Twin (P4)."""
        from grpclib.exceptions import GRPCError
        from grpclib.const import Status
        try:
            connectivity = await vehicle.get_connectivity()
            print(f"  Connectivity: {connectivity}")
        except GRPCError as e:
            assert e.status == Status.UNIMPLEMENTED
            print(f"  Connectivity: UNIMPLEMENTED ({e.message})")


class TestLiveParkingClimateTimers:
    """Test parking climate timer API endpoints."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_climate_timers(self, vehicle):
        """Test getting climate timers."""
        timers = await vehicle.get_climate_timers()
        assert isinstance(timers, list)
        print(f"  Climate timers: {len(timers)} scheduled")
        for timer in timers:
            print(f"    - {timer}")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_climate_timer_settings(self, vehicle):
        """Test getting climate timer settings. UNIMPLEMENTED on some vehicles."""
        from grpclib.exceptions import GRPCError
        from grpclib.const import Status
        try:
            settings = await vehicle.get_climate_timer_settings()
            assert settings is not None
            print(f"  Timer settings: {settings}")
        except GRPCError as e:
            assert e.status == Status.UNIMPLEMENTED
            print(f"  Timer settings: UNIMPLEMENTED ({e.message})")


# ============ WRITE COMMAND TESTS (Opt-in via environment variable) ============


class TestLiveWriteCommands:
    """Test write commands - DANGEROUS, disabled by default.

    Set POLESTAR_ENABLE_WRITE_TESTS=1 to enable these tests.
    Each test prompts for confirmation before execution.
    """

    @pytest.fixture
    def write_commands_enabled(self):
        """Check if write tests are enabled."""
        return os.environ.get("POLESTAR_ENABLE_WRITE_TESTS") == "1"

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_lock(self, vehicle, write_commands_enabled):
        """Test locking the car."""
        if not write_commands_enabled:
            pytest.skip("Set POLESTAR_ENABLE_WRITE_TESTS=1 to enable write tests")

        confirm = input("\n⚠️  Lock the car? (y/N): ").strip().lower()
        if confirm != 'y':
            pytest.skip("User declined")

        result = await vehicle.lock()
        assert result is not None

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_unlock(self, vehicle, write_commands_enabled):
        """Test unlocking the car."""
        if not write_commands_enabled:
            pytest.skip("Set POLESTAR_ENABLE_WRITE_TESTS=1 to enable write tests")

        confirm = input("\n⚠️  Unlock the car? (y/N): ").strip().lower()
        if confirm != 'y':
            pytest.skip("User declined")

        result = await vehicle.unlock()
        assert result is not None

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_start_climate(self, vehicle, write_commands_enabled):
        """Test starting climatization."""
        if not write_commands_enabled:
            pytest.skip("Set POLESTAR_ENABLE_WRITE_TESTS=1 to enable write tests")

        confirm = input("\n⚠️  Start climate? (y/N): ").strip().lower()
        if confirm != 'y':
            pytest.skip("User declined")

        result = await vehicle.start_climate()
        assert result is not None
        if result and result.response:
            print(f"  Start climate: {result.response.status.name}")
            assert result.response.status.name in ("SENT", "DELIVERED", "SUCCESS")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_start_climate_with_temp(self, vehicle, write_commands_enabled):
        """Test starting climatization with a target temperature."""
        if not write_commands_enabled:
            pytest.skip("Set POLESTAR_ENABLE_WRITE_TESTS=1 to enable write tests")

        temp_input = input("\n🌡️  Start climate with target temperature (°C), or Enter for 22.0: ").strip()
        try:
            temp = float(temp_input) if temp_input else 22.0
        except ValueError:
            temp = 22.0
        print(f"  Starting climate at {temp}°C...")
        result = await vehicle.start_climate(temperature=temp)
        assert result is not None
        if result and result.response:
            print(f"  Start climate {temp}°C: {result.response.status.name}")
            assert result.response.status.name in ("SENT", "DELIVERED", "SUCCESS")

        # Verify climate status reflects the change
        climate = await vehicle.get_climate()
        if climate is not None:
            print(f"  Climate status: running={climate.running_status.name}, active={climate.is_active}")

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_stop_climate(self, vehicle, write_commands_enabled):
        """Test stopping climatization."""
        if not write_commands_enabled:
            pytest.skip("Set POLESTAR_ENABLE_WRITE_TESTS=1 to enable write tests")

        confirm = input("\n⚠️  Stop climate? (y/N): ").strip().lower()
        if confirm != 'y':
            pytest.skip("User declined")

        result = await vehicle.stop_climate()
        assert result is not None
        if result and result.response:
            print(f"  Stop climate: {result.response.status.name}")
