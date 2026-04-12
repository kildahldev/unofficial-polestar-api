# unofficial-polestar-api

Unofficial async Python client for Polestar vehicle gRPC APIs.

This library does not give you any more control over your car than the official app, but it does expose functions that can be timed, macroed, controlled or displayed in apps like Home Assistant.

## Disclaimer

This project is not affiliated with, endorsed by, or in any way officially connected to Polestar, Volvo Cars, or any of their subsidiaries.

This library does not contain any proprietary code, or copyrighted material from Polestar or Volvo. All code is written from scratch by observing the behaviour of the official app.

All API interactions are based on reverse-engineered, undocumented interfaces. These may change or break without notice. Use at your own risk. The authors are not responsible for any consequences of using this software, including but not limited to vehicle malfunctions, warranty implications, or account restrictions.


## Supported Cars

This library implements the **C3** (Volvo Cars Cloud Connectivity) backend. The Polestar app actually supports four backends — C3, PCCS, Vocmo, and HuanFu — and the server assigns one per vehicle via a `remoteControlType` field.

The server assigns a backend per vehicle — which cars use which backend is unclear. Development and testing is done against a Polestar 4 (C3). Contributions and testing from owners of other models are welcome.

| Backend | Status |
|---|---|
| C3 | ✅ Implemented |
| PCCS | ❌ Not implemented |
| Vocmo | ❌ Not implemented |
| HuanFu | ❌ Not implemented |

Not all features are available on all models.


## Quick Start

```python
from polestar_api import PolestarApi

async with PolestarApi(email="you@example.com", password="...") as api:
    vehicles = await api.get_vehicles()
    car = vehicles[0]

    battery = await car.get_battery()
    print(f"{battery.charge_level}% — {battery.estimated_range_km} km")

    location = await car.get_location()
    print(f"Lat {location.latitude}, Lon {location.longitude}")
```

## Features

- **Battery** — charge level, range, charging status, power, temperatures (with real-time streaming)
- **Location** — last known and last parked position (with real-time streaming)
- **Climate** — start/stop climatization with target temperature, seat and steering wheel heating
- **Climate timers** — view and manage scheduled parking climate timers
- **Locks** — lock, unlock, trunk unlock
- **Honk & flash** — flash lights or honk+flash
- **Windows** — open/close all windows
- **Exterior** — door, window, sunroof, hood, tailgate, and alarm status
- **Dashboard** — trip meters, odometer, tyre pressure warnings, connectivity status
- **Charging** — target SOC, amp limit, charge timers, start/stop immediate charging
- **Charge locations** — full CRUD for saved locations with per-location amp limits, min SOC, timers, departure times, and smart charging
- **Health** — service warnings, fluid levels, tyre pressures (kPa), all exterior light warnings, 12V battery
- **Availability** — vehicle online status with unavailable reason
- **Weather** — temperature at car location
- **OTA** — software update info, scheduling, install now, cancel
- **Pre-cleaning** — air quality status (PM2.5, AQI) and start/stop cabin pre-cleaning

For the full API reference with all methods, models, and enums, see the [docs](docs/).

## Architecture

- **Auth**: OIDC/PKCE flow against Volvo/Polestar PingFederate with automatic token refresh
- **Discovery**: C3 endpoint resolution via `cnepmob.volvocars.com`, vehicle listing via MyStarV2 GraphQL
- **Transport**: gRPC over TLS using `grpclib`, no generated protobuf stubs — hand-written dataclasses with a custom wire codec
- **Token storage**: pluggable `TokenStore` protocol (file-based default, swap in your own for HA config entries)

## Documentation

Generate API reference docs from the codebase:

```bash
pip install -e '.[docs]'
mkdocs serve
```