## Live Activities & rich charging/climate notifications

Two automations that turn charging and climate (pre-conditioning) into an always-current notification on your phone: a **Live Activity** on iOS (Dynamic Island + Lock Screen) and a **Live Update** on Android — Home Assistant's own names for the same pair of features. Both come from the [Home Assistant Companion App](https://companion.home-assistant.io/)'s `notify.mobile_app_*` action and its [Live Activities / Live Updates](https://companion.home-assistant.io/docs/notifications/live-activities/) support — no extra integration or server needed.

### Platform support

Both automations call the same `notify.mobile_app_*` action with the same data; `live_update: true` (the field that starts/updates the activity) and most other fields below work on both platforms, so there is no per-OS branching to write.

> [!IMPORTANT]
> **Android needs a `title` on every call.** Without it, the notification posts as an ordinary banner instead of a Live Update. **iOS needs 17.2 or later and Home Assistant Core 2026.7.0 or newer**, and is not available on iPad.

- **iOS:** needs **17.2 or later** and **Home Assistant Core 2026.7.0+**. While the feature is in beta, check its status under the Companion App's own **Settings → Live Activities**, and that Home Assistant is allowed to send notifications at all under **iOS Settings → Home Assistant**. Not available on iPad (an Apple limitation). The first time an activity starts, iOS shows a one-time privacy disclosure.
- **Android:** needs `title` to be set on every call — without it, the notification posts as an ordinary banner instead of a Live Update. Some options need Android 16+, and Samsung phones may need **developer options → Live notifications for all apps** turned on.

> [!NOTE]
> Re-sending a notification with the same `tag` updates the existing activity in place instead of stacking a new one, on both platforms — that's what makes it "live". `tag` may only contain letters, numbers, hyphens and underscores, up to 64 characters (both examples below already comply).

### Setup

1. Find your entity prefix: look up a real entity such as `sensor.polestar_4_es59205_battery_level`; the prefix (here `polestar_4_es59205`) is what `polestar_VIN` stands for below.
2. Find your notify action: **Developer Tools → Actions**, search for `notify.mobile_app`, and use the result for your phone (e.g. `notify.mobile_app_pixel_9` or `notify.mobile_app_iphone`). Call it once per device/person if more than one phone should get the notification.
3. Paste one of the automations below into **Settings → Automations → ⋮ → Edit in YAML** (new automation), find-and-replace `polestar_VIN` and `notify.mobile_app_YOUR_DEVICE`, and adjust `url` to wherever your own Polestar dashboard lives (or remove the `url` line — it's just the tap target).
4. Both use `mode: restart` so a new trigger (e.g. the SoC changing) cancels and restarts the in-flight run rather than piling up.

### Charging Live Activity

Starts when charging begins, refreshes on SoC/ETA changes and every 5 minutes, and distinguishes "Charged" (target reached, still plugged in) from "Paused" (stopped but still plugged in) from a genuine stop. Routine refreshes are silent; only reaching Charged or Paused makes a sound. Clears automatically 30 minutes after Charged, or immediately on unplug.

```yaml
alias: Live Activity - Polestar charging
description: >-
  Single owner of the Polestar live activity (tag polestar-charging).
  Refreshes on SoC/ETA changes and every 5 min. All refreshes (including
  the start) are silent; only Charged (finished) and Paused (stopped) are
  audible. Keeps Charged for 30 min, clears on unplug.
mode: restart
triggers:
  - trigger: state
    entity_id: sensor.polestar_VIN_charging_status
    to: charging
    id: start
  - trigger: state
    entity_id: sensor.polestar_VIN_charging_status
    from: charging
    id: stopped
  - trigger: state
    entity_id: sensor.polestar_VIN_charging_status
    to: done
    for: "00:30:00"
    id: expire
  - trigger: state
    entity_id: sensor.polestar_VIN_charger_connection
    to: disconnected
    id: unplugged
  - trigger: time_pattern
    minutes: /5
    id: update
  - trigger: state
    entity_id:
      - sensor.polestar_VIN_battery_level
      - sensor.polestar_VIN_time_to_full
    id: soc
actions:
  - choose:
      - alias: Clear when unplugged or 30 min after charged
        conditions:
          - condition: trigger
            id: ["unplugged", "expire"]
        sequence:
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              message: clear_notification
              data:
                tag: polestar-charging
      - alias: Charged (finished or target reached, still plugged in)
        conditions:
          - condition: trigger
            id: stopped
          - condition: state
            entity_id: sensor.polestar_VIN_charging_status
            state: done
        sequence:
          - variables:
              soc: "{{ states('sensor.polestar_VIN_battery_level') | float(0) | round(0) | int }}"
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              title: Polestar
              message: "Charged · {{ soc }}%"
              data:
                tag: polestar-charging
                live_update: true
                critical_text: "{{ soc }}%"
                progress: "{{ soc }}"
                progress_max: 100
                notification_icon: mdi:battery-check
                notification_icon_color: "#FF7500"
                progress_bar_color: "#FF7500"
                url: /lovelace/polestar
                silent: false
      - alias: Paused (stopped but still plugged in)
        conditions:
          - condition: trigger
            id: stopped
          - condition: state
            entity_id: sensor.polestar_VIN_charging_status
            state: idle
          - condition: state
            entity_id: sensor.polestar_VIN_charger_connection
            state: connected
        sequence:
          - variables:
              soc: "{{ states('sensor.polestar_VIN_battery_level') | float(0) | round(0) | int }}"
              target: "{{ states('number.polestar_VIN_target_soc') | int(100) }}"
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              title: Polestar
              message: "Paused · plugged in · target {{ target }}%"
              data:
                tag: polestar-charging
                live_update: true
                critical_text: "{{ soc }}%"
                progress: "{{ soc }}"
                progress_max: 100
                notification_icon: mdi:ev-plug-type2
                notification_icon_color: "#ECECE7"
                progress_bar_color: "#ECECE7"
                url: /lovelace/polestar
                silent: false
    default:
      - alias: Let SoC, ETA and status sensors settle together
        delay: "00:00:05"
      - variables:
          soc: "{{ states('sensor.polestar_VIN_battery_level') | float(0) | round(0) | int }}"
          eta: "{{ states('sensor.polestar_VIN_time_to_full') | int(0) }}"
          finish: "{{ ((now().timestamp() + eta * 60) | int) if eta > 0 else 0 }}"
          kw: "{{ (states('sensor.polestar_VIN_charging_power') | float(0) / 1000) | round(1) }}"
          target: "{{ states('number.polestar_VIN_target_soc') | int(100) }}"
      - if:
          - condition: state
            entity_id: sensor.polestar_VIN_charging_status
            state: charging
        then:
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              title: "Polestar · {{ kw }} kW"
              message: "{{ 'Charging' if finish > now().timestamp() else 'Almost done' }} · target {{ target }}%"
              data:
                tag: polestar-charging
                live_update: true
                critical_text: "{{ soc }}%"
                progress: "{{ soc }}"
                progress_max: 100
                chronometer: "{{ finish > now().timestamp() }}"
                when: "{{ finish }}"
                when_relative: false
                notification_icon: mdi:ev-station
                notification_icon_color: "#FF7500"
                progress_bar_color: "#FF7500"
                url: /lovelace/polestar
                silent: true
      - alias: Refresh Charged when SoC/ETA arrives late
        if:
          - condition: state
            entity_id: sensor.polestar_VIN_charging_status
            state: done
          - condition: trigger
            id: soc
        then:
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              title: Polestar
              message: "Charged · {{ soc }}%"
              data:
                tag: polestar-charging
                live_update: true
                critical_text: "{{ soc }}%"
                progress: "{{ soc }}"
                progress_max: 100
                notification_icon: mdi:battery-check
                notification_icon_color: "#FF7500"
                progress_bar_color: "#FF7500"
                url: /lovelace/polestar
                silent: true
```

### Climate (pre-conditioning) Live Activity

Shows a running countdown while the cabin climate/pre-conditioning is active, however it was started (timer, app, key fob, or Home Assistant). Clears immediately if stopped early; otherwise shows "Done" and clears 5 minutes later, or as soon as a door opens (the periodic refresh also pauses while a door is open, so it doesn't fight with someone walking up to the car).

```yaml
alias: Live Activity - Polestar climate
description: >-
  Live activity (tag polestar-climate) while the Polestar's cabin
  climate/pre-conditioning is running. Driven by the climate-active binary
  sensor and the car's own time-remaining sensor, so the countdown runs on
  the phone. Silent updates. Clears at once if stopped before its 30
  minutes are up, otherwise shows Done and clears 5 min after it stops, or
  as soon as any door is opened.
mode: restart
triggers:
  - trigger: state
    entity_id: binary_sensor.polestar_VIN_climate_active
    to: "on"
    id: start
  - trigger: state
    entity_id: binary_sensor.polestar_VIN_climate_active
    to: "off"
    id: stop
  - trigger: state
    entity_id: binary_sensor.polestar_VIN_climate_active
    to: "off"
    for: "00:05:00"
    id: clear
  - trigger: time_pattern
    minutes: /5
    id: update
  - trigger: state
    entity_id: binary_sensor.polestar_VIN_any_door_open
    from: "off"
    to: "on"
    id: clear
actions:
  - choose:
      - alias: Clear 5 min after it stops, or as soon as a door is opened
        conditions:
          - condition: trigger
            id: clear
        sequence:
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              message: clear_notification
              data:
                tag: polestar-climate
      - alias: "Stopped early: clear at once instead of showing Done"
        conditions:
          - condition: trigger
            id: stop
          - condition: template
            value_template: >-
              {{ (now() - trigger.from_state.last_changed).total_seconds() < 28 * 60 }}
        sequence:
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              message: clear_notification
              data:
                tag: polestar-climate
      - alias: Climate stopped
        conditions:
          - condition: trigger
            id: stop
        sequence:
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              title: Polestar · Climate
              message: Climate finished
              data:
                tag: polestar-climate
                live_update: true
                critical_text: Done
                notification_icon: mdi:check-circle
                notification_icon_color: "#FF7500"
                url: /lovelace/polestar
                silent: true
    default:
      - alias: Let the time-remaining sensor update with the status
        delay: "00:00:05"
      - if:
          - condition: state
            entity_id: binary_sensor.polestar_VIN_climate_active
            state: "on"
          - condition: state
            entity_id: binary_sensor.polestar_VIN_any_door_open
            state: "off"
        then:
          - variables:
              mins: "{{ states('sensor.polestar_VIN_climate_time_remaining') | int(0) }}"
              finish: "{{ (now().timestamp() + mins * 60) | int }}"
              source: >-
                {% set r = states('sensor.polestar_VIN_climate_request_type') %}
                {{ '' if r in ['undefined', 'unknown', 'unavailable'] else r | replace('_', ' ') | capitalize }}
              outside: "{{ states('sensor.polestar_VIN_outside_temperature') | float(none) }}"
          - action: notify.mobile_app_YOUR_DEVICE
            data:
              title: Polestar · Climate
              message: >-
                {{ ['Pre-conditioning', source, (outside | round(0) | int ~ '°C outside') if outside is not none else ''] | select | join(' · ') }}
              data:
                tag: polestar-climate
                live_update: true
                critical_text: A/C
                chronometer: "{{ mins > 0 }}"
                when: "{{ finish }}"
                when_relative: false
                notification_icon: mdi:fan
                notification_icon_color: "#FF7500"
                progress_bar_color: "#FF7500"
                url: /lovelace/polestar
                silent: true
```

### Plain notifications instead

> [!TIP]
> If you'd rather get a normal (non-persistent) notification at the start/stop/finish of charging than an always-on Live Activity, trigger on the same `sensor.polestar_VIN_charging_status` and `sensor.polestar_VIN_charger_connection` state changes, but call `notify.mobile_app_YOUR_DEVICE` without `tag`/`live_update`/`progress` — each call then shows as its own notification instead of updating one in place. `data: {push: {interruption-level: passive}}` (iOS only; Android ignores it) is useful for a "plugged in but not yet charging" note you don't want to make a sound.

### Troubleshooting

- **Nothing shows up as a Live Activity on iOS:** check the feature's status under the Companion App's own **Settings → Live Activities**, confirm Home Assistant can send notifications at all under **iOS Settings → Home Assistant**, and that the automation actually fired — check **Settings → Automations → (the automation) → trace**. Not available on iPad.
- **Shows as a plain banner on Android instead of an updating Live Update:** the call is missing `title` — Android requires it to recognise the notification as a Live Update at all.
- **Android notification doesn't update in place:** make sure every call in the automation uses the exact same `tag` — a different tag creates a separate notification instead of replacing the existing one. Some devices (Samsung in particular) also need **developer options → Live notifications for all apps** enabled.
- **Activity stopped updating after repeated start/stop while testing:** iOS enforces a "push-to-start" budget; rapidly starting and ending activities while iterating on the automation can make new ones silently fail to start for a while. Space out test runs, or wait and retry.
- **Long-running climate/charging session stops updating:** both platforms cap how long a single activity can run (iOS: up to 8 hours) before the OS ends it on its own: not usually a factor for charging/climate, but worth knowing if you adapt these for something longer-running.
- **Stale Charged/Done card that won't clear:** the `clear_notification` actions rely on `tag` matching too; if you changed the tag partway through testing, send one `clear_notification` call with the old tag to remove the orphaned card.
