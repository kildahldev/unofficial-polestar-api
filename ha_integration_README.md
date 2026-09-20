# Unofficial Polestar for Home Assistant

Unofficial Home Assistant custom integration for Polestar vehicles. Communicates with Polestar's gRPC backend directly via [`unofficial-polestar-api`](https://pypi.org/project/unofficial-polestar-api/).

## Install

Requires [HACS](https://hacs.xyz/) installed on your Home Assistant instance.

1. In HA, go to **HACS → ⋮ (top right) → Custom repositories**
2. Paste `kildahldev/unofficial-polestar-api` and select **Integration**
3. Click **Add**, then find **Unofficial Polestar** in HACS and click **Download**
4. Restart Home Assistant

Then add the integration via **Settings → Devices & Services → Add Integration → Polestar**. Enter your Polestar ID email and password — the integration discovers the cars on your account and lets you **pick your vehicle from a list** and set the polling interval. Each config entry sets up one vehicle — to add more than one car, add the integration again and pick the other vehicle.

- **Secondary / guest accounts** (no vehicles listed): choose **"My vehicle is not listed"** and enter the VIN (Vehicle Identification Number) manually.
- **Demo mode:** tick **Demo mode** on the first step and enter any VIN to get a fake vehicle with static data (no API connection needed).

## Changing your Polestar email or password

If your Polestar ID password (or email) changes, you don't need to remove and re-add the integration. The existing entry is kept, so all entities, history and dashboards carry over.

- **Sign-in stops working:** Home Assistant prompts you to re-authenticate. Enter the current password, and update the email too if it changed.
- **Change it proactively:** open the integration under **Settings → Devices & Services → Polestar**, click **⋮** on the vehicle entry and choose **Reconfigure**.

The new credentials are checked before they are saved, and the account must have access to the same vehicle (VIN) as the entry it replaces. Guest / secondary accounts, which don't list any vehicles, are accepted.

## Entities

Each vehicle gets ~106 entities when all features are available:
Features vary between models, and are yet to be fully documented

| Platform | Count | Examples |
|----------|-------|---------|
| Sensor | 48 | Battery level, charging status, availability reason, climate status, health warnings, tyre pressures, charge locations |
| Binary sensor | 25 | Charging, plugged in, locked, doors, windows, hood, tailgate, tank lid, available |
| Device tracker | 2 | GPS location, parked location |
| Lock | 1 | Central lock |
| Switch | 4 | Climate, pre-cleaning, charging, charge timer |
| Number | 4 | Target SOC, charging amp limit, climate target temperature, timer target temperature |
| Button | 7 | Flash lights, honk, honk and flash, refresh, open/close windows, unlock trunk |
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
