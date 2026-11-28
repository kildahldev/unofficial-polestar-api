

# unofficial-polestar-api

Unofficial async Python client and Home Assistant integration for Polestar gRPC APIs.

This project aims to bring you as much control as possible over your car. It uses the same APIs as the official mobile app and exposes most functionality.

## Supported Cars

This library implements the **C3** (Volvo Cars Cloud Connectivity) backend.
If you use this library (or the HA integration) please report back what works and what doesn't, for your model.
Contributions and testing from owners of other models are welcome and encouraged  
Not all features are available on all models. Look at the features list for some comments on different models.

## Usage

### Home Assistant

[![Open your Home Assistant instance and open the repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kildahldev&repository=unofficial-polestar-api&category=integration)

Unofficial Polestar is in the default community store, so you don't need to add a custom repository.

- **Home Assistant 2026.11 or newer:** go to **Settings → Marketplace**, search for **Unofficial Polestar** and select **Install**.
- **Older versions:** install [HACS](https://hacs.xyz/), then open **HACS**, search for **Unofficial Polestar**, click **Download** and restart Home Assistant.

**Beta versions:** in the Marketplace, open Unofficial Polestar → ⋮ → **Include pre-releases**. In HACS, use ⋮ → **Redownload**, turn on **Show beta versions** and pick the beta.

Then add the integration via **Settings → Devices & Services → Add Integration → Polestar**. Enter your Polestar ID email and password — the integration discovers the cars on your account and lets you **pick your vehicle from a list** and set the polling interval. Each config entry sets up one vehicle — to add more than one car, add the integration again and pick the other vehicle.

- **Secondary / guest accounts** (no vehicles listed): choose **"My vehicle is not listed"** and enter the VIN (Vehicle Identification Number) manually.
- **Demo mode:** tick **Demo mode** on the first step and enter any VIN to get a fake vehicle with static data (no API connection needed).

See the [HA integration README](ha_integration_README.md) for setup, entities, services, and dashboard cards.

### As a library


    python  
    from polestar_api import PolestarApi  
      
    async with PolestarApi(email="you@example.com", password="...") as api:  
     vehicles = await api.get_vehicles() car = vehicles[0]  
     battery = await car.get_battery() print(f"{battery.charge_level}% — {battery.range_km} km")  
     location = await car.get_location() print(f"Lat {location.coordinate.latitude}, Lon {location.coordinate.longitude}") 

## Features

- **Battery** — charge level, range, charging status, power (with real-time streaming)
- **Location** — last known and last parked position (with real-time streaming)
- **Climate** — start/stop climatization with target temperature, seat and steering wheel heating
- **Climate timers** — view and manage scheduled parking climate timers
- **Locks** — lock, unlock, trunk unlock
- **Honk & flash** — flash lights or honk+flash
- **Windows** — open/close all windows
- **Exterior** — door, window, sunroof, hood, tailgate, and alarm status.
- **Charging** — target SOC, amp limit, charge timers, start/stop immediate charging
- **Charge locations** — full CRUD for saved locations with per-location amp limits, min SOC, timers, departure times, and smart charging
- **Health** — service warnings, fluid levels, tyre pressures (kPa), all exterior light warnings, 12V battery
- **Availability** — vehicle online status with unavailable reason
- **Weather** — temperature at car location
- **OTA** — software update info, scheduling, install now, cancel
- **Pre-cleaning** — air quality status (PM2.5, AQI) and start/stop cabin pre-cleaning

For the full API reference with all methods, models, and enums, see the [docs](https://kildahldev.github.io/unofficial-polestar-api/).

### Feature availability by model

Not all features are available on all models. Unsupported commands are
detected at runtime — the corresponding HA entities become unavailable
automatically and re-enable if a future software update adds support.

| Feature | Polestar 2 | Polestar 3 | Polestar 4 |
|---------|:----------:|:----------:|:----------:|
| Battery | ✅ | ✅ | ✅ |
| Location / parked location | ✅ | ✅ | ✅ |
| Climate (start/stop/temp/seats) | ✅ | ✅ | ✅ |
| Climate timers (list) | ✅ | ✅ | ✅ |
| Climate timer settings | ✅ | ✅ | ❌ |
| Lock / unlock | ✅ | ✅ | ✅ |
| Trunk unlock | ✅ | ✅ | ✅ |
| Honk & flash | ✅ | ✅ | ✅ |
| Windows open/close | ✅ | ✅ | ❌ |
| Exterior status | ✅ | ✅ | ✅ |
| Charging start/stop | ✅ | ✅ | ✅ |
| Target SOC | ✅ | ✅ | ✅ |
| Amp limit | ✅ | ✅ | ❌ |
| Charge timer | ✅ | ✅ | ✅ |
| Charge locations | ✅ | ✅ | ✅ |
| Health (tyre pressures) | ❌ (no TPMS) | ✅ | ✅ |
| Availability | ✅ | ✅ | ✅ |
| Weather | ✅ | ✅ | ✅ |
| OTA software info | ✅ | ✅ | ✅ |
| OTA schedule / install / cancel | ✅ | ✅ | ❓ |
| Pre-cleaning | ✅ | ✅ | ✅ |
| Dashboard (legacy PCCS) | ✅ | ❌ | ❌ |
| Connectivity (legacy PCCS) | ✅ | ❌ | ❌ |

> **Note:** Availability was tested on a Polestar 4 (software version as of Jul 2026).
> Polestar 2 and 3 columns are based on community reports and may vary by
> software version. Please report back what works and what doesn't for your model.

## FAQ

**The charging switch doesnt work?**
It uses the same `StartOverride`/`StopOverrideChargeTimer` calls as the official app, which only override an *active* charge schedule. If no schedule is active (the car is charging freely),
there's nothing to override, so the switch has no effect. I have yet to find an API to directly start/stop a charge session.
The only ways to stop a free charge is to set a charge schedule that excludes the current time, or to set the target SOC lower than the current SOC.

## Disclaimer

This project is not affiliated with, endorsed by, or in any way officially connected to Polestar, Volvo Cars, or any of their subsidiaries.

This library does not contain any proprietary code, or copyrighted material from Polestar or Volvo. All code is written from scratch by observing the behaviour of the official app.

All API interactions are based on reverse-engineered, undocumented interfaces. These may change or break without notice. Use at your own risk. The authors are not responsible for any consequences of using this software, including but not limited to vehicle malfunctions, warranty implications, or account restrictions.
