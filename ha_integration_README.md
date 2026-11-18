# Polestar C3 for Home Assistant

Unofficial Home Assistant custom integration for Polestar vehicles. Communicates with Polestar's gRPC backend directly via [`unofficial-polestar-api`](https://pypi.org/project/unofficial-polestar-api/).

## What's new

- **Diagnostics**: download a diagnostics report from **Settings → Devices & Services → Polestar → ⋮ → Download diagnostics**. It includes each vehicle's data snapshot, stream health, and a count of API calls made per endpoint (redacted — no VIN, email, or GPS coordinates).
- **Charging-time sensors**: four new diagnostic sensors estimate the time to reach your target charge level at domestic (7kW), low (22kW), fast (100kW), and ultrafast (300kW) charging power, based on your model's battery capacity. They have a value whether or not the car is actually plugged in.
- **Commands no longer look "undone"**: locking, unlocking, and starting/stopping climate used to sometimes show the new state, revert, then correct itself minutes later. Fixed by making sure a slower background refresh can no longer overwrite a more recent one, and by holding the shown state until the car actually confirms the change.
- **Fewer unnecessary cloud calls**: endpoints your car doesn't support (common on some models) are now re-probed once a day instead of every 30 minutes, and are skipped entirely by the refresh that follows a command. Entities also only re-render when a value actually changes, rather than on every poll and stream update.
- **More resilient streaming**: a transient network hiccup on a live stream (battery, location, exterior, etc.) is now retried instead of failing outright, and reconnects are throttled so a flaky connection can't turn into a tight request loop.
- *(Earlier this cycle)* Renamed to **Polestar C3**, Air Purification toggle, Connected Services / data-sharing consent entities, boot lock merged into a dedicated **Boot lock** entity, capability-based entity disabling (unsupported sensors like tyre pressure no longer show as unavailable), and single-flight token refresh with a re-login cooldown.

## Install

Requires [HACS](https://hacs.xyz/) installed on your Home Assistant instance.

1. In HA, go to **HACS → ⋮ (top right) → Custom repositories**
2. Paste `BeauGiles/ha-polestar-c3` and select **Integration**
3. Click **Add**, then find **Polestar C3** in HACS and click **Download**
4. Restart Home Assistant

Then add the integration via **Settings → Devices & Services → Add Integration → Polestar**. Enter your Polestar ID email and password — the integration discovers the cars on your account and lets you **pick your vehicle from a list** and set the polling interval. Each config entry sets up one vehicle — to add more than one car, add the integration again and pick the other vehicle.

- **Secondary / guest accounts** (no vehicles listed): choose **"My vehicle is not listed"** and enter the VIN (Vehicle Identification Number) manually.
- **Demo mode:** tick **Demo mode** on the first step and enter any VIN to get a fake vehicle with static data (no API connection needed).

## Entities

Each vehicle gets ~114 entities when all features are available:
Features vary between models, and are yet to be fully documented

| Platform | Count | Examples |
|----------|-------|---------|
| Sensor | 56 | Battery level, charging status, availability reason, climate status/temperature/seat heating, health warnings, tyre pressures, charge locations |
| Binary sensor | 26 | Charging, plugged in, locked, doors, windows, hood, tailgate, tank lid, available, remote function data sharing |
| Device tracker | 2 | GPS location, parked location |
| Lock | 2 | Central lock, boot lock (unlock opens the boot; lock relocks the whole car) |
| Switch | 5 | Climate, pre-cleaning, charging, charge timer, Air Purification *(alias of pre-cleaning; disabled by default)* |
| Number | 4 | Target SOC, charging amp limit, climate target temperature, timer target temperature |
| Button | 6 | Flash lights, honk, honk and flash, refresh, open/close windows |
| Select | 11 | Target SOC mode, climate start seat/steering heating, climate timer default seat/steering heating and battery preconditioning |
| Time | 2 | Charge timer start and stop |
| Calendar | 3 | Parking climate timer slots |
| Update | 1 | OTA software update |

Entity IDs are generated from the vehicle model and registration. For example, a Polestar 4 registered `ES59205` will create entities like `sensor.polestar_4_es59205_battery_level`, `lock.polestar_4_es59205_lock`, and `button.polestar_4_es59205_refresh`.

## Update interval

The integration polls the Polestar cloud for updates every **10 minutes** by default. To change this:

1. Go to **Settings → Devices & Services → Polestar**
2. Click **Configure** on your vehicle entry
3. Set the **Polling interval** (in seconds, minimum 60, maximum 86400)

Lower values give faster updates but may increase server load and 12v battery drain. In addition to polling, the integration keeps long-lived streams open for real-time updates (battery, location, door status, etc.), so polling mainly covers data that isn't streamed.

## Services

The integration also registers custom services for the parts of the Polestar API that do not fit a single HA entity cleanly:

- `polestar.start_climate`
- `polestar.set_charge_timer`
- `polestar.clear_charge_timer`
- `polestar.create_charge_location`
- `polestar.update_charge_location`
- `polestar.delete_charge_location`
- `polestar.schedule_ota`
- `polestar.cancel_ota`
- `polestar.delete_climate_timer`
