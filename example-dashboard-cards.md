## Dashboard Cards

Below are some opinionated configurations for a dashboard setup

### Home Overview Card
<img width="820" height="159" alt="image" src="https://github.com/user-attachments/assets/dafec2ab-6062-469c-8558-5fd8affba28f" />

Requires [mushroom-cards](https://github.com/piitaya/lovelace-mushroom) and [card-mod](https://github.com/thomasloven/lovelace-card-mod) via HACS. Shows battery level, range, charging status, lock state, and plug status with a battery progress bar.

**Setup:** Find-and-replace `polestar_VIN` with your entity prefix. The easiest way to find it is to look up a real entity such as `sensor.polestar_4_es59205_battery_level`; the prefix is the middle part, here `polestar_4_es59205`.

```yaml
type: custom:mushroom-template-card
entity: sensor.polestar_VIN_battery_level
primary: Polestar 4
secondary: >-
  {% set battery_raw = states('sensor.polestar_VIN_battery_level') %}
  {% set range_raw = states('sensor.polestar_VIN_range') %}
  {%- set minutes = states('sensor.polestar_VIN_time_to_full_charge') | int(0) -%}
  {%- set battery = states('sensor.polestar_VIN_battery_level') | float(0) -%}
  {%- set charging_status = states('sensor.polestar_VIN_charging_status') -%}
  {%- set lock_state = states('lock.polestar_VIN_lock') -%}
  {{ battery | round(0) if is_number(battery_raw) else '--' }}% ·
  {{ range_raw | float(0) | round(0) if is_number(range_raw) else '--' }} km
  {%- if charging_status == 'charging' and minutes > 0 %} · ⚡ {{ minutes }} min
  {%- elif battery >= 100 %} · Full
  {%- elif charging_status in ['unknown', 'unavailable'] %} · Charging status unavailable
  {%- else %} · {{ charging_status | replace('_', ' ') | title }}
  {%- endif %} ·
  {{ lock_state | replace('_', ' ') | title if lock_state not in ['unknown', 'unavailable'] else 'Lock unavailable' }}
  {%- if is_state('binary_sensor.polestar_VIN_plugged_in', 'on') %} · Plugged in{% endif %}
icon: mdi:car-electric
icon_color: >-
  {% set battery_raw = states('sensor.polestar_VIN_battery_level') %}
  {% set battery = battery_raw | float(0) %}
  {% set charging = states('sensor.polestar_VIN_charging_status') == 'charging' %}
  {% if not is_number(battery_raw) %}disabled{% elif battery >= 100 %}green{% elif charging %}cyan{% elif battery > 50 %}green
  {% elif battery > 20 %}amber{% else %}red{% endif %}
layout: horizontal
tap_action:
  action: navigate
  navigation_path: /polestar-car
card_mod:
  style: |
    ha-card {
      overflow: hidden;
      position: relative;
      padding-bottom: 6px;
    }
    ha-card::before {
      content: '';
      position: absolute;
      left: 0; right: 0; bottom: 0;
      height: 6px;
      background: rgba(148, 163, 184, 0.22);
    }
    ha-card::after {
      content: '';
      position: absolute;
      left: 0; bottom: 0;
      height: 6px;
      width: calc(100% * {{ states('sensor.polestar_VIN_battery_level') | float(0) / 100 }});
      max-width: 100%;
      background: {% set battery = states('sensor.polestar_VIN_battery_level') | float(0) %}
        {% set charging = states('sensor.polestar_VIN_charging_status') == 'charging' %}
        {% if battery >= 100 %}#22c55e{% elif charging %}#06b6d4
        {% elif battery > 50 %}#22c55e{% elif battery > 20 %}#f59e0b{% else %}#ef4444{% endif %};
      transition: width 1s ease, background 0.4s ease;
    }
```

### Vehicle Status Card
<img width="843" height="742" alt="image" src="https://github.com/user-attachments/assets/58f4cbc2-8449-4aa1-a891-0783d6d640ea" />

Install [vehicle-status-card](https://github.com/ngocjohn/vehicle-status-card) via HACS, plus `Mushroom` and `card-mod` for the popup controls.

**Setup:** Find-and-replace all occurrences of `polestar_VIN` with your entity prefix (for example `polestar_4_es59205`). Verify the first few replacements against real entities in **Developer Tools → States** before pasting the full card.

<details>
<summary>Full vehicle-status-card YAML</summary>

```yaml
type: custom:vehicle-status-card
name: Polestar 4

images:
  - image: /polestar/static/Polestar4.png

range_info:
  - energy_level:
      entity: sensor.polestar_VIN_battery_level
      icon: mdi:battery-charging-70
      value_position: inside
    charging:
      charging_entity: binary_sensor.polestar_VIN_charging
    charge_target:
      charge_target_entity: number.polestar_VIN_target_soc
      charge_target_color: "#ffffff"
    progress_color: "#d4a84b"
    bar_height: 20
    bar_radius: 10
  - energy_level:
      entity: sensor.polestar_VIN_range
      icon: mdi:map-marker-distance
      value_position: inside
      max_value: 500
    progress_color: "#5b8fb9"
    bar_height: 14
    bar_radius: 7

indicator_rows:
  - row_items:
      - type: entity
        entity: lock.polestar_VIN_lock
        icon: mdi:lock
        state_color: true
        tap_action:
          action: toggle
        show_state: true
      - type: entity
        entity: binary_sensor.polestar_VIN_plugged_in
        icon: mdi:ev-plug-type2
        state_color: true
        show_state: true
      - type: entity
        entity: sensor.polestar_VIN_outside_temperature
        icon: mdi:thermometer
        show_state: true
    alignment: center
    no_wrap: true
  - row_items:
      - type: entity
        entity: binary_sensor.polestar_VIN_available
        icon: mdi:car-connected
        state_color: true
        show_state: true
      - type: group
        name: Doors
        icon: mdi:car-door
        items:
          - entity: binary_sensor.polestar_VIN_any_door_open
            name: Any door
            state_color: true
          - entity: binary_sensor.polestar_VIN_front_left_door
            name: Front left
            state_color: true
          - entity: binary_sensor.polestar_VIN_front_right_door
            name: Front right
            state_color: true
          - entity: binary_sensor.polestar_VIN_rear_left_door
            name: Rear left
            state_color: true
          - entity: binary_sensor.polestar_VIN_rear_right_door
            name: Rear right
            state_color: true
      - type: group
        name: Windows
        icon: mdi:window-closed-variant
        items:
          - entity: binary_sensor.polestar_VIN_front_left_window
            name: Front left
            state_color: true
          - entity: binary_sensor.polestar_VIN_front_right_window
            name: Front right
            state_color: true
          - entity: binary_sensor.polestar_VIN_rear_left_window
            name: Rear left
            state_color: true
          - entity: binary_sensor.polestar_VIN_rear_right_window
            name: Rear right
            state_color: true
      - type: group
        name: Warnings
        icon: mdi:alert-circle-outline
        items:
          - entity: binary_sensor.polestar_VIN_tyre_warning
            name: Tyres
            state_color: true
          - entity: binary_sensor.polestar_VIN_light_failure
            name: Lights
            state_color: true
          - entity: binary_sensor.polestar_VIN_hood
            name: Hood
            state_color: true
          - entity: binary_sensor.polestar_VIN_tailgate
            name: Tailgate
            state_color: true
          - entity: binary_sensor.polestar_VIN_sunroof
            name: Sunroof
            state_color: true
          - entity: binary_sensor.polestar_VIN_tank_lid
            name: Tank lid
            state_color: true
          - entity: binary_sensor.polestar_VIN_service_required
            name: Service
            state_color: true
          - entity: binary_sensor.polestar_VIN_low_voltage_battery
            name: 12V battery
            state_color: true
    alignment: center
    no_wrap: true

button_cards:
  # -- Climate --
  - name: Climate
    icon: mdi:air-conditioner
    entity: switch.polestar_VIN_climate
    state_color: true
    show_secondary: true
    tap_action:
      action: toggle
    card_type: custom
    button_type: default
    sub_card:
      title: Climate & Air
      custom_card:
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: switch.polestar_VIN_climate
              primary: Climate
              secondary: "{{ states('switch.polestar_VIN_climate') | title }}"
              icon: mdi:air-conditioner
              icon_color: >-
                {% if is_state('switch.polestar_VIN_climate', 'on') %}blue
                {% else %}disabled{% endif %}
              tap_action:
                action: toggle
              layout: vertical
              fill_container: true
              multiline_secondary: true
            - type: custom:mushroom-template-card
              entity: switch.polestar_VIN_pre_cleaning
              primary: Pre-clean
              secondary: "{{ states('switch.polestar_VIN_pre_cleaning') | title }}"
              icon: mdi:air-purifier
              icon_color: >-
                {% if is_state('switch.polestar_VIN_pre_cleaning', 'on') %}teal
                {% else %}disabled{% endif %}
              tap_action:
                action: toggle
              layout: vertical
              fill_container: true
              multiline_secondary: true
        - type: custom:mushroom-template-card
          entity: calendar.polestar_VIN_parking_climate_timer_1
          primary: "Timer 1 · {{ state_attr('calendar.polestar_VIN_parking_climate_timer_1', 'ready_at') or 'Not set' }}"
          secondary: >-
            {% set act = state_attr('calendar.polestar_VIN_parking_climate_timer_1', 'activated') %}
            {% set days = state_attr('calendar.polestar_VIN_parking_climate_timer_1', 'weekdays') or [] %}
            {% if act == None %}Not configured{% elif not act %}Inactive
            {% elif days | length == 7 %}Every day
            {% elif days | length == 5 and 'saturday' not in days and 'sunday' not in days %}Weekdays
            {% elif days | length == 2 and 'saturday' in days and 'sunday' in days %}Weekends
            {% else %}{{ days | map('replace','monday','Mon') | map('replace','tuesday','Tue') | map('replace','wednesday','Wed') | map('replace','thursday','Thu') | map('replace','friday','Fri') | map('replace','saturday','Sat') | map('replace','sunday','Sun') | join(', ') }}{% endif %}
            {% if act and state_attr('calendar.polestar_VIN_parking_climate_timer_1', 'repeat') %} · Repeating{% endif %}
          icon: mdi:calendar-clock
          icon_color: "{% if state_attr('calendar.polestar_VIN_parking_climate_timer_1', 'activated') %}green{% else %}disabled{% endif %}"
          tap_action:
            action: more-info
          layout: horizontal
        - type: custom:mushroom-template-card
          entity: calendar.polestar_VIN_parking_climate_timer_2
          primary: "Timer 2 · {{ state_attr('calendar.polestar_VIN_parking_climate_timer_2', 'ready_at') or 'Not set' }}"
          secondary: >-
            {% set act = state_attr('calendar.polestar_VIN_parking_climate_timer_2', 'activated') %}
            {% set days = state_attr('calendar.polestar_VIN_parking_climate_timer_2', 'weekdays') or [] %}
            {% if act == None %}Not configured{% elif not act %}Inactive
            {% elif days | length == 7 %}Every day
            {% elif days | length == 5 and 'saturday' not in days and 'sunday' not in days %}Weekdays
            {% elif days | length == 2 and 'saturday' in days and 'sunday' in days %}Weekends
            {% else %}{{ days | map('replace','monday','Mon') | map('replace','tuesday','Tue') | map('replace','wednesday','Wed') | map('replace','thursday','Thu') | map('replace','friday','Fri') | map('replace','saturday','Sat') | map('replace','sunday','Sun') | join(', ') }}{% endif %}
            {% if act and state_attr('calendar.polestar_VIN_parking_climate_timer_2', 'repeat') %} · Repeating{% endif %}
          icon: mdi:calendar-clock
          icon_color: "{% if state_attr('calendar.polestar_VIN_parking_climate_timer_2', 'activated') %}green{% else %}disabled{% endif %}"
          tap_action:
            action: more-info
          layout: horizontal
        - type: custom:mushroom-template-card
          entity: calendar.polestar_VIN_parking_climate_timer_3
          primary: "Timer 3 · {{ state_attr('calendar.polestar_VIN_parking_climate_timer_3', 'ready_at') or 'Not set' }}"
          secondary: >-
            {% set act = state_attr('calendar.polestar_VIN_parking_climate_timer_3', 'activated') %}
            {% set days = state_attr('calendar.polestar_VIN_parking_climate_timer_3', 'weekdays') or [] %}
            {% if act == None %}Not configured{% elif not act %}Inactive
            {% elif days | length == 7 %}Every day
            {% elif days | length == 5 and 'saturday' not in days and 'sunday' not in days %}Weekdays
            {% elif days | length == 2 and 'saturday' in days and 'sunday' in days %}Weekends
            {% else %}{{ days | map('replace','monday','Mon') | map('replace','tuesday','Tue') | map('replace','wednesday','Wed') | map('replace','thursday','Thu') | map('replace','friday','Fri') | map('replace','saturday','Sat') | map('replace','sunday','Sun') | join(', ') }}{% endif %}
            {% if act and state_attr('calendar.polestar_VIN_parking_climate_timer_3', 'repeat') %} · Repeating{% endif %}
          icon: mdi:calendar-clock
          icon_color: "{% if state_attr('calendar.polestar_VIN_parking_climate_timer_3', 'activated') %}green{% else %}disabled{% endif %}"
          tap_action:
            action: more-info
          layout: horizontal
        - type: entities
          title: Comfort
          show_header_toggle: false
          entities:
            - entity: number.polestar_VIN_timer_target_temperature
              name: Temperature
            - entity: select.polestar_VIN_timer_front_left_seat_heat
              name: Front left seat
              icon: mdi:car-seat-heater
            - entity: select.polestar_VIN_timer_front_right_seat_heat
              name: Front right seat
              icon: mdi:car-seat-heater
            - entity: select.polestar_VIN_timer_rear_left_seat_heat
              name: Rear left seat
              icon: mdi:car-seat-heater
            - entity: select.polestar_VIN_timer_rear_right_seat_heat
              name: Rear right seat
              icon: mdi:car-seat-heater
            - entity: select.polestar_VIN_timer_steering_wheel_heat
              name: Steering wheel
              icon: mdi:steering
            - entity: select.polestar_VIN_timer_battery_preconditioning
              name: Battery precond.
              icon: mdi:battery-heart-variant
        - type: entities
          title: Status
          show_header_toggle: false
          entities:
            - entity: binary_sensor.polestar_VIN_climate_active
              name: Active
            - entity: sensor.polestar_VIN_climate_running_status
              name: Status
            - entity: sensor.polestar_VIN_climate_time_remaining
              name: Time left
            - entity: sensor.polestar_VIN_air_quality_index
              name: Air quality
            - entity: sensor.polestar_VIN_pm2_5
              name: PM2.5
            - entity: sensor.polestar_VIN_outside_temperature
              name: Outside temp

  # -- Lock --
  - name: Lock
    icon: mdi:car-key
    entity: lock.polestar_VIN_lock
    state_color: true
    show_secondary: true
    tap_action:
      action: toggle
    card_type: custom
    button_type: default
    sub_card:
      title: Lock & Security
      custom_card:
        - type: custom:mushroom-template-card
          entity: lock.polestar_VIN_lock
          primary: Central Lock
          secondary: >-
            {% if is_state('lock.polestar_VIN_lock', 'locking') %}Locking
            {% elif is_state('lock.polestar_VIN_lock', 'unlocking') %}Unlocking
            {% else %}{{ states('lock.polestar_VIN_lock') | title }}{% endif %}
          icon: >-
            {% if is_state('lock.polestar_VIN_lock', 'locking') or is_state('lock.polestar_VIN_lock', 'unlocking') %}mdi:loading
            {% elif is_state('lock.polestar_VIN_lock', 'locked') %}mdi:lock
            {% else %}mdi:lock-open-variant{% endif %}
          icon_color: >-
            {% if is_state('lock.polestar_VIN_lock', 'locking') or is_state('lock.polestar_VIN_lock', 'unlocking') %}amber
            {% elif is_state('lock.polestar_VIN_lock', 'locked') %}green
            {% else %}orange{% endif %}
          tap_action:
            action: toggle
          layout: horizontal
          multiline_secondary: true
          card_mod:
            style: |
              ha-state-icon {
                {% if is_state('lock.polestar_VIN_lock', 'locking') or is_state('lock.polestar_VIN_lock', 'unlocking') %}
                animation: spin 1s linear infinite;
                {% endif %}
              }
              @keyframes spin { to { transform: rotate(360deg); } }
        - type: entities
          title: Doors
          show_header_toggle: false
          entities:
            - entity: binary_sensor.polestar_VIN_any_door_open
              name: Any door open
              icon: mdi:car-door
            - entity: binary_sensor.polestar_VIN_front_left_door
              name: Front left
              icon: mdi:car-door
            - entity: binary_sensor.polestar_VIN_front_right_door
              name: Front right
              icon: mdi:car-door
            - entity: binary_sensor.polestar_VIN_rear_left_door
              name: Rear left
              icon: mdi:car-door
            - entity: binary_sensor.polestar_VIN_rear_right_door
              name: Rear right
              icon: mdi:car-door
            - entity: binary_sensor.polestar_VIN_hood
              name: Hood
              icon: mdi:car
            - entity: binary_sensor.polestar_VIN_tailgate
              name: Tailgate
              icon: mdi:car-back

  # -- Charging --
  - name: Charging
    icon: mdi:ev-station
    entity: switch.polestar_VIN_charging
    state_color: true
    show_secondary: true
    tap_action:
      action: toggle
    card_type: custom
    button_type: default
    sub_card:
      title: Charging
      custom_card:
        - type: custom:mushroom-template-card
          entity: switch.polestar_VIN_charging
          primary: Charging
          secondary: "{{ states('switch.polestar_VIN_charging') | title }}"
          icon: mdi:ev-station
          icon_color: >-
            {% if is_state('switch.polestar_VIN_charging', 'on') %}green
            {% else %}disabled{% endif %}
          tap_action:
            action: toggle
          layout: horizontal
          multiline_secondary: true
        - type: entities
          title: Charge Window
          show_header_toggle: false
          entities:
            - entity: switch.polestar_VIN_charge_timer
              name: Charge timer
              icon: mdi:timer-outline
            - entity: time.polestar_VIN_charge_timer_start
              name: Charge from
              icon: mdi:clock-start
            - entity: time.polestar_VIN_charge_timer_stop
              name: Charge until
              icon: mdi:clock-end
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: select.polestar_VIN_target_soc_mode
              primary: Daily
              secondary: "40–90%"
              icon: mdi:calendar-today
              icon_color: >-
                {% if states('select.polestar_VIN_target_soc_mode') == 'daily' %}blue
                {% else %}disabled{% endif %}
              tap_action:
                action: call-service
                service: select.select_option
                data:
                  entity_id: select.polestar_VIN_target_soc_mode
                  option: daily
              layout: vertical
              multiline_secondary: true
            - type: custom:mushroom-template-card
              entity: select.polestar_VIN_target_soc_mode
              primary: Long Trip
              secondary: "90–100%"
              icon: mdi:highway
              icon_color: >-
                {% if states('select.polestar_VIN_target_soc_mode') == 'long_trip' %}orange
                {% else %}disabled{% endif %}
              tap_action:
                action: call-service
                service: select.select_option
                data:
                  entity_id: select.polestar_VIN_target_soc_mode
                  option: long_trip
              layout: vertical
              multiline_secondary: true
            - type: custom:mushroom-template-card
              entity: select.polestar_VIN_target_soc_mode
              primary: Custom
              secondary: "{{ states('number.polestar_VIN_target_soc') }}%"
              icon: mdi:tune-variant
              icon_color: >-
                {% if states('select.polestar_VIN_target_soc_mode') == 'custom' %}green
                {% else %}disabled{% endif %}
              tap_action:
                action: call-service
                service: select.select_option
                data:
                  entity_id: select.polestar_VIN_target_soc_mode
                  option: custom
              layout: vertical
              multiline_secondary: true
        - type: conditional
          conditions:
            - entity: select.polestar_VIN_target_soc_mode
              state: custom
          card:
            type: entities
            show_header_toggle: false
            entities:
              - entity: number.polestar_VIN_target_soc
                name: Target charge level
        - type: entities
          show_header_toggle: false
          entities:
            - entity: number.polestar_VIN_charging_amp_limit
              name: Amp limit
        - type: entities
          title: Live
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_charging_status
              name: Status
            - entity: sensor.polestar_VIN_charger_connection
              name: Connection
            - entity: sensor.polestar_VIN_charging_type
              name: Type
            - entity: sensor.polestar_VIN_charger_power_status
              name: Power source
            - entity: sensor.polestar_VIN_charging_power
              name: Power
            - entity: sensor.polestar_VIN_charging_current
              name: Current
            - entity: sensor.polestar_VIN_charging_voltage
              name: Voltage
            - entity: sensor.polestar_VIN_time_to_full_charge
              name: Time to full
            - entity: sensor.polestar_VIN_time_to_target_charge
              name: Time to target
            - entity: sensor.polestar_VIN_time_to_minimum_soc
              name: Time to minimum
        - type: entities
          title: Location
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_current_charge_location
              name: Current location
            - entity: binary_sensor.polestar_VIN_at_charge_location
              name: At saved location
            - entity: sensor.polestar_VIN_charge_locations
              name: Saved locations

  # -- Vehicle Info (includes Software & Tyres) --
  - name: Vehicle
    icon: mdi:car-info
    entity: sensor.polestar_VIN_odometer
    show_secondary: true
    card_type: custom
    button_type: default
    sub_card:
      title: Vehicle Info
      custom_card:
        - type: entities
          title: Odometer & Trips
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_odometer
              name: Odometer
            - entity: sensor.polestar_VIN_trip_meter_manual
              name: Trip (manual)
            - entity: sensor.polestar_VIN_trip_meter_auto
              name: Trip (auto)
        - type: entities
          title: Consumption
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_average_consumption
              name: Average
            - entity: sensor.polestar_VIN_average_consumption_auto
              name: Average (auto)
            - entity: sensor.polestar_VIN_average_consumption_since_charge
              name: Since charge
        - type: entities
          title: Connectivity
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_usage_mode
              name: Usage mode
        - type: entities
          title: Service & Warnings
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_distance_to_service
              name: Distance to service
            - entity: sensor.polestar_VIN_days_to_service
              name: Days to service
            - entity: sensor.polestar_VIN_engine_hours_to_service
              name: Hours to service
            - entity: sensor.polestar_VIN_service_warning
              name: Service
            - entity: sensor.polestar_VIN_brake_fluid_warning
              name: Brake fluid
            - entity: sensor.polestar_VIN_washer_fluid_warning
              name: Washer fluid
            - entity: sensor.polestar_VIN_low_voltage_battery_warning
              name: 12V battery
        - type: entities
          show_header_toggle: false
          entities:
            - entity: update.polestar_VIN_software_update
              name: OTA update
            - entity: sensor.polestar_VIN_software_version
              name: Installed version
            - entity: sensor.polestar_VIN_software_state
              name: Update state
        - type: entities
          title: Tyre Pressures
          show_header_toggle: false
          entities:
            - entity: sensor.polestar_VIN_front_left_tyre_pressure
              name: Front left
            - entity: sensor.polestar_VIN_front_right_tyre_pressure
              name: Front right
            - entity: sensor.polestar_VIN_rear_left_tyre_pressure
              name: Rear left
            - entity: sensor.polestar_VIN_rear_right_tyre_pressure
              name: Rear right

  # -- Actions (Trunk, Windows, Flash, Honk, Refresh) --
  - name: Actions
    icon: mdi:car-cog
    card_type: custom
    button_type: default
    sub_card:
      title: Actions
      custom_card:
        - type: custom:mushroom-template-card
          entity: button.polestar_VIN_unlock_trunk
          primary: Unlock Trunk
          secondary: Tap to unlock
          icon: mdi:car-back
          icon_color: blue
          tap_action:
            action: call-service
            service: button.press
            data:
              entity_id: button.polestar_VIN_unlock_trunk
          layout: horizontal
          multiline_secondary: true
        - type: entities
          show_header_toggle: false
          entities:
            - entity: binary_sensor.polestar_VIN_tailgate
              name: Tailgate
              icon: mdi:car-back
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: button.polestar_VIN_open_windows
              primary: Open All
              secondary: Tap to open
              icon: mdi:window-open-variant
              icon_color: blue
              tap_action:
                action: call-service
                service: button.press
                data:
                  entity_id: button.polestar_VIN_open_windows
              layout: vertical
              fill_container: true
              multiline_secondary: true
            - type: custom:mushroom-template-card
              entity: button.polestar_VIN_close_windows
              primary: Close All
              secondary: Tap to close
              icon: mdi:window-closed-variant
              icon_color: blue
              tap_action:
                action: call-service
                service: button.press
                data:
                  entity_id: button.polestar_VIN_close_windows
              layout: vertical
              fill_container: true
              multiline_secondary: true
        - type: entities
          show_header_toggle: false
          entities:
            - entity: binary_sensor.polestar_VIN_front_left_window
              name: Front left
            - entity: binary_sensor.polestar_VIN_front_right_window
              name: Front right
            - entity: binary_sensor.polestar_VIN_rear_left_window
              name: Rear left
            - entity: binary_sensor.polestar_VIN_rear_right_window
              name: Rear right
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: button.polestar_VIN_flash_lights
              primary: Flash
              secondary: Tap to flash
              icon: mdi:car-light-high
              icon_color: blue
              tap_action:
                action: call-service
                service: button.press
                data:
                  entity_id: button.polestar_VIN_flash_lights
              layout: vertical
              fill_container: true
              multiline_secondary: true
            - type: custom:mushroom-template-card
              entity: button.polestar_VIN_honk_and_flash
              primary: Honk & Flash
              secondary: Tap to honk & flash
              icon: mdi:bugle
              icon_color: blue
              tap_action:
                action: call-service
                service: button.press
                data:
                  entity_id: button.polestar_VIN_honk_and_flash
              layout: vertical
              fill_container: true
              multiline_secondary: true
        - type: horizontal-stack
          cards:
            - type: custom:mushroom-template-card
              entity: button.polestar_VIN_refresh
              primary: Refresh
              secondary: Tap to refresh
              icon: mdi:refresh
              icon_color: blue
              tap_action:
                action: call-service
                service: button.press
                data:
                  entity_id: button.polestar_VIN_refresh
              layout: horizontal
              fill_container: true
              multiline_secondary: true

layout_config:
  button_grid:
    rows: 2
    columns: 3
    swipe: false
  images_swipe:
    max_height: 180
    max_width: 500
    autoplay: true
    loop: true
    delay: 5000
    speed: 600
    effect: slide
    hide_pagination: false
  range_info_config:
    layout: column
  section_order:
    - images
    - range_info
    - indicators
    - buttons
  theme_config:
    theme: default
```

</details>
