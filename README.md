# Polestar C3 — Home Assistant integration

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BeauGiles&repository=ha-polestar-c3&category=integration)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Native Home Assistant custom integration for Polestar cars on Volvo Cars' C3 platform, using the same services as the Polestar app. Battery, location, doors, locks, climate, charging settings and more, with live updates streamed from the car's cloud and commands sent back through the same channel.

The matching integration for Volvo cars is [Volvo C3](https://github.com/BeauGiles/ha-volvo-c3). The two talk to the same backend and share entity names, states and behaviour.

> [!WARNING]
> **Unofficial and unsupported.** This is a community project. It is **not made, endorsed or supported by Polestar or Volvo Cars**. It uses the same private services as the Polestar app, not an official API, and they can change or be blocked at any time without notice.
>
> **Check the official option first.** If you live in Austria, Belgium, Luxembourg, Denmark, Estonia, Finland, France, Germany, Iceland, Ireland, Italy, Latvia, Lithuania, the Netherlands, Norway, Portugal, Spain or Sweden, Polestar offers an official [Data Portal](https://data-portal.polestar.com). Use that if it meets your needs. Use this integration only where it isn't available or doesn't offer what you need.

> [!NOTE]
> **Why "Polestar C3"?** The name tells this integration apart from the web-based GraphQL [Polestar API](https://github.com/pypolestar/polestar_api) integration (`polestar_api`). This one uses the C3 gRPC services that the Polestar app itself uses, which is why it has live streams, command results and the car's own capability flags. You do not need `polestar_api` alongside it.

## Supported cars

Built and tested on a **Polestar 2**. The integration implements the C3 backend, so other models should work, but features differ between them and not every model has been tested. The integration asks the car which features it supports and hides the rest, so a missing entity usually means the car doesn't offer it.

Reports of what works and what doesn't on your model are welcome. Please [open an issue](https://github.com/BeauGiles/ha-polestar-c3/issues).

## Features

[Volvo C3](https://github.com/BeauGiles/ha-volvo-c3) and Polestar C3 talk to the same Volvo Cars C3 platform, so most features are the same. This table is shared by both READMEs.

✅ supported · 🧪 experimental (limited testing) · ◐ only on cars that report it · ➖ not available

### Read

| Feature | Volvo C3 | Polestar C3 |
| --- | :---: | :---: |
| State of charge, range | ✅ | ✅ |
| Charging status, power, current, voltage, charger connection | ✅ | ✅ |
| Time to full charge | ✅ | ✅ |
| Time to target charge and to minimum SoC | ➖ | ✅ |
| Charge port, plugged in | ✅ | ✅ |
| Saved charge locations, "at charge location" | ➖ | ✅ |
| Location, with address | ✅ | ✅ |
| Parked location, altitude, heading, speed | ➖ | ✅ |
| Doors, windows, hood, tailgate | ✅ | ✅ |
| Sunroof | ◐ | ➖ |
| Central lock, boot lock | ✅ | ✅ |
| Alarm triggered, In use, Online, Connection | ✅ | ✅ |
| Odometer, trip meters, average consumption, average speed | ✅ | ✅ (average speed hidden on the Polestar 2) |
| Outside temperature | ✅ | ✅ |
| Service required (with urgency), days, distance and engine hours to service | ✅ | ✅ |
| Tyre warning, per-wheel grades | ◐ | ◐ |
| Per-wheel tyre pressures | ◐ | ◐ |
| 12V battery, brake fluid, washer fluid, light status | ✅ | ✅ |
| Engine coolant, oil level (combustion cars) | ◐ | ➖ |
| Climate status and time remaining | ➖ | ✅ |
| Cabin air quality | ✅ | ✅ |
| Software version | ✅ | ✅ |
| Driving journal: last trip, trips and distance this month (opt in) | ✅ | ➖ |
| VIN, vehicle info, registration plate | ✅ | ✅ |

### Control

| Feature | Volvo C3 | Polestar C3 |
| --- | :---: | :---: |
| Lock, unlock, lock with reduced alarm | ✅ | ✅ |
| Boot lock (unlock the tailgate only) | ✅ | ✅ |
| Open and close tailgate | ✅ | ➖ |
| Flash lights, honk, honk and flash | ✅ | ✅ |
| Open and close all windows | ✅ | ✅ |
| Start and stop climate | ✅ | ✅ |
| Climate target temperature | ◐ | ◐ |
| Seat and steering wheel heating | 🧪 ◐ | ◐ |
| Engine remote start (starts cabin climate on an EV) | ✅ | ➖ |
| Air purification | ✅ | ✅ |
| Target SoC, charging amp limit | ✅ | ✅ |
| Charging schedule: switch, start and end times | ✅ | ✅ |
| Start and stop charging | ✅ | ✅ |
| Parking climate timers (calendars) | ➖ | ✅ |
| Software update: schedule, install, cancel | ➖ | ✅ |
| Manage saved charge locations (services) | ➖ | ✅ |

### Behaviour

| Feature | Volvo C3 | Polestar C3 |
| --- | :---: | :---: |
| Clear error when a command is refused (offline, privacy mode, in use, busy, timeout) | 🧪 | ✅ |
| Live updates streamed from the car's cloud | 🧪 | ✅ |
| Adaptive polling (faster while charging, driving or running climate) | ✅ | ✅ |
| Entities hidden for features the car doesn't have | ✅ | ✅ |
| Reconfigure flow, diagnostics download | ✅ | ✅ |
| Demo mode | ➖ | ✅ |
| More than one car (one entry per car) | ✅ | ✅ |

> [!CAUTION]
> These commands act on a real car. You are responsible for how you use them and for any automations you build on them.

## Entities

| Platform | Examples |
| --- | --- |
| Sensor | State of charge, range, charging status, charger connection, climate status, odometer, service sensors, tyre pressures, software version, Connection, Vehicle info |
| Binary sensor | Online, In use, Plugged in, Alarm triggered, Tyre warning, Service required, 12V battery, Brake fluid, Washer fluid, Light status, doors, windows, hood, tailgate, charge port |
| Device tracker | Location, Parked location |
| Lock | Lock, Boot lock |
| Switch | Climate, Charging, Charging schedule, Air purification |
| Number | Target SoC, Charging amp limit, Climate target temperature, Timer target temperature |
| Select | Seat and steering wheel heating, Target SoC mode, timer heating and battery preconditioning |
| Button | Flash lights, Honk, Honk and flash, Lock with reduced alarm, Open and Close windows, Refresh |
| Time | Charging schedule start and end |
| Calendar | Three parking climate timer slots (in the Configuration category and off by default) |
| Update | Software update |

Entity IDs come from the car model and registration, for example `sensor.polestar_2_abc123_battery_level`. Which entities appear depends on what the car supports.

## Install

Requires [HACS](https://hacs.xyz/) on your Home Assistant instance.

1. In HACS, open **⋮ → Custom repositories**.
2. Add `https://github.com/BeauGiles/ha-polestar-c3` with category **Integration**.
3. Find **Polestar C3** in HACS and click **Download**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration → Polestar C3**.

Enter your Polestar ID email and password. The integration finds the cars on your account and lets you pick one. Each entry sets up one car, so to add a second car add the integration again and pick the other one.

> [!TIP]
> **Secondary or guest accounts** (no cars listed): choose **My vehicle is not listed** and enter the VIN. Using a secondary account that has been given access to your car, not your main account, is a good idea.

> [!NOTE]
> **Demo mode:** tick **Demo mode** on the first step and enter any VIN to get a fake car with static data and no connection to Polestar.

### Updating

> [!IMPORTANT]
> After updating, **restart Home Assistant**. A reload is not enough. Read the [changelog](CHANGELOG.md) first, because some updates change sensor states or remove entities.

## Options

Open **Settings → Devices & Services → Polestar C3 → Configure**.

- **Polling interval** (default 10 minutes): how often data that is not streamed is fetched, such as charging settings, odometer, charge locations and weather.
- **Active polling interval:** a shorter interval used while the car is charging, being driven or running climate, and for a few minutes after a trip.
- **Registration plate** (optional): shown on the device.

Battery, location, doors and locks are streamed in real time, so polling mainly covers the rest.

## Services

The integration registers services for the parts of the Polestar API that do not fit a single entity:

- `polestar.start_climate`
- `polestar.set_charge_timer`
- `polestar.clear_charge_timer`
- `polestar.create_charge_location`
- `polestar.update_charge_location`
- `polestar.delete_charge_location`
- `polestar.schedule_ota`
- `polestar.cancel_ota`
- `polestar.delete_climate_timer`

Details and fields are in **Developer tools → Actions**.

## Notifications and Live Activities

Example automations for a charging and a climate (preconditioning) Live Activity on iOS and Android: see [example-live-activities.md](example-live-activities.md). Example dashboard cards are in [example-dashboard-cards.md](example-dashboard-cards.md).

## FAQ

**The charging switch doesn't do anything.**
It uses the same start and stop override calls as the Polestar app, which only override an *active* charging schedule. If no schedule is active and the car is charging freely, there is nothing to override. A reliable way to stop a free charge is to set a charging schedule that excludes the current time, or to set the target SoC below the current level.

**Setup or reauth says Polestar wants this account to finish a step first.**
Since late November 2026 some Polestar ID accounts are asked for one more step after the password, usually a one-time code sent by text message to verify the phone number. It happens once per account. Home Assistant can't enter the code, so sign in once at [polestar.com](https://www.polestar.com) or in the Polestar app with the same account, enter the code there, then try again in Home Assistant. Accepting new terms works the same way. Until then, the integration stops signing in on its own, so it won't keep sending you codes.

**An entity is missing.**
The integration hides entities for features the car says it doesn't have (for example tyre pressures on a car without TPMS, or the climate settings on a car without rear seat settings). The Polestar 2 does not send average speed.

**Something stopped working.**
Download diagnostics from **Settings → Devices & Services → Polestar C3 → ⋮ → Download diagnostics**. It is redacted (no VIN, email or GPS) and includes stream health and a count of API calls per endpoint. Attach it to an issue.

## For developers

The code that speaks to Polestar's servers is a Python library in `src/polestar_api`. It is bundled into the integration in `custom_components/polestar/vendor`, so Home Assistant needs no extra install. Run `python scripts/sync_vendor.py` after changing it, and `uv run pytest` for the tests.

The upstream project publishes an [API reference](https://kildahldev.github.io/unofficial-polestar-api/) for the library, with all methods, models and enums. This fork has changed since it was taken (for example, the older PCCS backend was removed), so treat the reference as a guide and check the code in `src/polestar_api` for the details.

A design for sharing this library with Volvo C3 is in the [Volvo C3 repository](https://github.com/BeauGiles/ha-volvo-c3/blob/main/docs/design-shared-c3-library.md).

## Credits

This started as a fork of [kildahldev/unofficial-polestar-api](https://github.com/kildahldev/unofficial-polestar-api) (MIT) and has since been reworked. Thanks to its author and the contributors whose fixes were taken from the upstream project: mvillarejo, ericyew, Martin Leisssoo (`MartinLeisssoo`), vladyspavlov, Rick van der Staaij (`rick-nu`) and TheOriginal92. See the [changelog](CHANGELOG.md) for what came from where.

## ☕ Support

If this saved you some time and you'd like to support me, you can leave a tip at [b3.au/tip-jar](https://b3.au/tip-jar).

## License

MIT, see [LICENSE](./LICENSE).

## Disclaimer

This project is independent. It is not affiliated with, authorised by, endorsed by or supported by Polestar, Volvo Cars, or any of their subsidiaries. "Polestar", "Volvo" and related names and logos are trademarks of their owners and are used only to say which cars this works with.

> [!WARNING]
> **Unofficial access.** It was built by reverse engineering how the Polestar app talks to the C3 platform's servers. It does not use an official, published API. The services can change at any time, with no warning and no migration path.

- **Terms of service.** Using it may breach the Polestar or Volvo Cars terms of service, and could lead to your account being limited or blocked. Consider using a secondary account that has been given access to your car.
- **It controls a real car.** Commands such as lock, unlock, start climate and start or stop charging act on your actual vehicle. You are responsible for how you use them, and for automations you build on them. Do not rely on this for anything safety critical.
- **Your credentials.** Sign-in tokens are stored in your Home Assistant configuration. Protect your Home Assistant backups and access accordingly.
- **No warranty and no support from Polestar or Volvo.** Use it at your own risk. It is provided as is, as set out in the licence. The authors are not responsible for any consequences of using it, including vehicle malfunctions, warranty implications or account restrictions. **Please do not contact Polestar, Volvo Cars or a dealer for help with this integration**; open an issue here instead.

### Official options

If you live in Austria, Belgium, Luxembourg, Denmark, Estonia, Finland, France, Germany, Iceland, Ireland, Italy, Latvia, Lithuania, the Netherlands, Norway, Portugal, Spain or Sweden, you can use Polestar's official [Data Portal](https://data-portal.polestar.com). This integration exists for people outside those countries, or who need something the official option doesn't provide.
