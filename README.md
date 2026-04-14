
# unofficial-polestar-api

Unofficial async Python client and Home Assistant integration for Polestar gRPC APIs.

This project aims to bring you as much control as possible over your car. It uses the same APIs as the official mobile app and exposes most functionality (Atleast for the PS4 for now)

> **Note on 12v battery impact:** This library communicates with Polestar's cloud servers, not the car directly. It polls the server every 10 minutes (default, configurable in HA) but it also keeps long lived streams open to the cloud to listen to changes (Battery, Location, Door status etc). It is unclear how much this affects the 12v battery.
If you have the opportunity, please monitor your battery voltage and report back.
## Supported Cars

This library for now just implements the **C3** (Volvo Cars Cloud Connectivity) backend. The Polestar app actually supports four backends — C3, PCCS, Vocmo, and HuanFu — and the server assigns one per vehicle via a `remoteControlType` field.

The server assigns a backend per vehicle — which cars use which backend is currently unclear, but the Polestar 4 (Which i developed against) - responds to commands through the C3 Backend. 

If you use this library (or the HA integration) please report back what works and what doesn't, for your model.

Contributions and testing from owners of other models are welcome and encouraged

| Model      | Backend | Verified         |
|------------|---------|------------------|
| Polestar 4 | C3      | ✅ Mostly working |
| Polestar 2 | C3      | ✅ Mostly working |
| Polestar 3 | C3      | ✅ Mostly working |

Not all features are available on all models. Look at the features list for some comments on different models.

## Usage

### Home Assistant

Requires [HACS](https://hacs.xyz/) installed on your Home Assistant instance.

1. In HA, go to **HACS → ⋮ (top right) → Custom repositories**
2. Paste `kildahldev/unofficial-polestar-api` and select **Integration**
3. Click **Add**, then find **Unofficial Polestar** in HACS and click **Download**
4. Restart Home Assistant

Then add the integration via **Settings → Devices & Services → Add Integration → Polestar**. Enter your Polestar ID email, password, and VIN (Vehicle Identification Number). Each config entry sets up one vehicle — add the integration again with a different VIN if you have multiple cars. Tick **Demo mode** to get a fake vehicle with static data (no API connection needed).

See the [HA integration README](ha_integration_README.md) for setup, entities, services, and dashboard cards.

### As a library

```python
from polestar_api import PolestarApi

async with PolestarApi(email="you@example.com", password="...") as api:
    vehicles = await api.get_vehicles()
    car = vehicles[0]

    battery = await car.get_battery()
    print(f"{battery.charge_level}% — {battery.range_km} km")

    location = await car.get_location()
    print(f"Lat {location.coordinate.latitude}, Lon {location.coordinate.longitude}")
```

## Features

- **Battery** — charge level, range, charging status, power (with real-time streaming)
- **Location** — last known and last parked position (with real-time streaming)
- **Climate** — start/stop climatization with target temperature, seat and steering wheel heating
- **Climate timers** — view and manage scheduled parking climate timers
- **Locks** — lock, unlock, trunk unlock
- **Honk & flash** — flash lights or honk+flash
- **Windows** — open/close all windows
- **Exterior** — door, window, sunroof, hood, tailgate, and alarm status
- **Charging** — target SOC, amp limit, charge timers, start/stop immediate charging *(Someo of these appear to be unavailable on Polestar 4)*
- **Charge locations** — full CRUD for saved locations with per-location amp limits, min SOC, timers, departure times, and smart charging
- **Health** — service warnings, fluid levels, tyre pressures (kPa), all exterior light warnings, 12V battery *(Tyre pressure is unavailable on Polestar 2 as it does not have TPMS)*
- **Availability** — vehicle online status with unavailable reason
- **Weather** — temperature at car location
- **OTA** — software update info, scheduling, install now, cancel *(Appears to be unavailable on Polestar 4)*
- **Pre-cleaning** — air quality status (PM2.5, AQI) and start/stop cabin pre-cleaning *(Appears to be unavailable on Polestar 4)*

For the full API reference with all methods, models, and enums, see the [docs](https://kildahldev.github.io/unofficial-polestar-api/).

## Disclaimer

This project is not affiliated with, endorsed by, or in any way officially connected to Polestar, Volvo Cars, or any of their subsidiaries.

This library does not contain any proprietary code, or copyrighted material from Polestar or Volvo. All code is written from scratch by observing the behaviour of the official app.

All API interactions are based on reverse-engineered, undocumented interfaces. These may change or break without notice. Use at your own risk. The authors are not responsible for any consequences of using this software, including but not limited to vehicle malfunctions, warranty implications, or account restrictions.
