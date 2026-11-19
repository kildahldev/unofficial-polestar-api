# Changelog

All notable changes to Polestar C3 (domain `polestar`), the Home Assistant integration in this repository. This integration and [Volvo C3](https://github.com/BeauGiles/ha-volvo-c3) talk to the same Volvo C3 backend and were brought in line with each other on 18 and 19 November 2026, so most entries here have a matching entry in the Volvo changelog.

Dates are 2026. The version in `manifest.json` has not been bumped.

## Unreleased (18 to 19 November)

### Read this before updating

- **Sensor states are lowercase keys.** Charging status, Charger connection, Usage mode and the other enum sensors report keys such as `charging`, `idle`, `scheduled`, `done`, `connected`, `disconnected`, `driving`, and the frontend shows translated text. Automations and dashboards that compare to `Charging`, `Idle` or `Connected` must use the lowercase keys. Charging status: `charging, idle, scheduled, discharging, error, smart_charging, done, smart_charging_paused`. Charger connection: `connected, disconnected, fault`. Usage mode: `abandoned, inactive, convenience, active, driving, engine_on, engine_off`.
- **The Connection sensor state is short:** `Online`, `Offline: <short reason>` or `Unknown`. The longer explanation and `offline_since` are attributes.
- **Entities were removed or merged** (see Removed). Their registry entries are deleted at setup, and the data they showed moved to attributes on the surviving entity.
- **Display names changed**, entity IDs did not.
- **Climate target temperature and the front seat and steering wheel heating selects are hidden on cars without rear seat settings** (the Polestar 2). The car record has no separate flags for these, so this is a heuristic: a car with front heating but no rear heating would lose them too.
- The three parking climate timer calendars are in the Configuration category and off by default. Existing installs keep their registry state; disable or enable them in the entity settings.
- **Why it is called "Polestar C3":** the integration was renamed (11 November) to tell it apart from the web-based GraphQL "Polestar API" integration (`polestar_api`). This one uses the C3 gRPC services that the Polestar app itself uses, which is why it has live streams, command results and the car's capability flags that the GraphQL one cannot offer. Keeping the two names distinct also avoids confusing their entities in Home Assistant.
- `polestar_api` (the older GraphQL integration) is not needed. Move automations and dashboards to this integration's entities before removing it.

### Harmonised with Volvo C3

- Shared entity names in sentence case: Service required, 12V battery, Brake fluid, Washer fluid, Front left door and window, Charge port, Online, State of charge, Outside temperature, Time to full charge, Trip meter (auto) and (manual), Cabin air quality index, Flash lights, Honk and flash, Lock with reduced alarm, Charging amp limit, Target SoC and Target SoC mode, Climate target temperature, Front left seat heating (and the other seats and steering wheel; the timer ones are "Timer front left seat heating"), Climate, Air purification, Charging schedule with Charging schedule start and end, Boot lock.
- Same stored state vocabulary and translated display states as Volvo, whole-number display by default for distance, range, battery, speed and times, entity categories, and the same attribute names for warnings.
- Same behaviour: Start charging is refused with a clear message when the car is not plugged in; Alarm triggered shows OK instead of Unknown when no alarm is reported; In use follows the availability reason; reconfigure flow; entity names from translations; entities hidden for features the car says it lacks.
- Config entry named like Volvo's: model and year.

### Added

- **Tyre warning grade:** per-wheel attributes (`ok`, `very_low`, `low`, `high`) on cars that report individual tyre pressures. Individual pressure sensors appear only on those cars.
- **Service required** attributes `service_urgency` (`almost_due`, `due`, `overdue`) and `service_reason` (`regular`, `engine_hours`, `distance`).
- **Plain-English command failures:** car offline, privacy mode on, car being driven, another command in progress, timeouts. "undefined" is never shown.
- **Average speed** and **Average speed (auto)** sensors. They are hidden when the car sends no value, which is the case on the Polestar 2.
- **Alarm triggered**, **In use**, **Light status** (one attribute per light), fluid and warning problem sensors, and a once-a-minute availability refresh.
- **Adaptive polling:** a shorter interval while charging, driving or running climate, and for 5 minutes after a trip.
- **Lock with reduced alarm**, **Location address**, **Boot lock** (merged with the old Unlock trunk button), **Connection** sensor, **VIN** sensor with model year, battery capacity, internet activation, build week, a verbose **Vehicle info** sensor with one attribute per field, optional registration plate.
- Combustion-only entities are hidden on electric cars.
- Capability gating from the car's own record: charge locations, window and sunroof control, target SoC presets, average consumption sensors, rear seat heating, climate timer slots, tyre pressure, service warning, air purification, honk, flash, light warnings.
- Diagnostics download, reconfigure flow, live streams, and the single-flight token refresh and endpoint handling carried over from the November 11 rework.

### Changed

- **Cabin air quality index** now reports PM2.5 in µg/m³ (PM2.5 device class), like Volvo's, and the separate PM2.5 sensor is gone. The entity keeps its old ID.
- **Target SoC and Charging amp limit** are re-read every minute, so changes made in the Polestar app show up within about a minute. The app does not push these.
- Charge locations are hidden when the car has none saved.
- The privacy setting is read in the background so its timeout no longer stalls polls.
- The vendored `polestar_api` library replaces the PyPI dependency.

### Removed

- **Last seen sensor.** It changed every few seconds while charging and filled the activity log. Connection keeps `offline_since`.
- **PM2.5 sensor** (merged into Cabin air quality index).
- **Target SOC sensor** (the Target SoC number shows it).
- **Duplicate Pre-cleaning switch** (one Air Purification switch remains) and the pre-cleaning runtime, start reason and error sensors, which are now attributes of the Air purification switch.
- **Climate sensors** for end time, current temperature, target temperature, seat and steering wheel heating: attributes of the Climate switch, and the heating selects show the choice.
- **Four assumed-power Charging time sensors.**
- **Remote function data sharing (privacy) sensor** and its background fetch.
- **Sunroof sensor** (the Polestar 2 has none).
- Other duplicate entities, with their data folded into the switches.

### Fixed

- Vehicle info attributes are JSON safe (raw bytes used to break state updates).
- The Tyre warning is no longer hidden on cars that omit the tyre warning flag.
- The charge timer switch reads off, not unknown, when no timer is set.
- Software info returns at once when empty and falls back to the installed version from the car record.
