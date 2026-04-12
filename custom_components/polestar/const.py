"""Constants for the Polestar integration."""

DOMAIN = "polestar"
CONF_DEMO = "demo"
CONF_VIN = "vin"

PLATFORMS = [
    "sensor",
    "binary_sensor",
    "device_tracker",
    "lock",
    "switch",
    "number",
    "button",
    "select",
    "time",
    "calendar",
    "update",
]

UPDATE_INTERVAL = 300  # seconds
STREAM_RETRY_DELAY = 30  # seconds

SERVICE_START_CLIMATE = "start_climate"
SERVICE_SET_CHARGE_TIMER = "set_charge_timer"
SERVICE_CLEAR_CHARGE_TIMER = "clear_charge_timer"
SERVICE_CREATE_CHARGE_LOCATION = "create_charge_location"
SERVICE_UPDATE_CHARGE_LOCATION = "update_charge_location"
SERVICE_DELETE_CHARGE_LOCATION = "delete_charge_location"
SERVICE_SCHEDULE_OTA = "schedule_ota"
SERVICE_CANCEL_OTA = "cancel_ota"
SERVICE_DELETE_CLIMATE_TIMER = "delete_climate_timer"

ATTR_ENTITY_ID = "entity_id"
ATTR_VIN = "vin"
ATTR_LOCATION_ID = "location_id"
ATTR_TIMER_ID = "timer_id"
