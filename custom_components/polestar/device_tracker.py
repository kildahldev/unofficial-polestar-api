"""Device tracker platform for Polestar integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PolestarEntity


@dataclass(frozen=True, kw_only=True)
class PolestarTrackerDescription(EntityDescription):
    """Tracker description."""

    data_attr: str = ""


TRACKERS: tuple[PolestarTrackerDescription, ...] = (
    PolestarTrackerDescription(key="location", name="Location", data_attr="location"),
    PolestarTrackerDescription(key="parked_location", name="Parked location", data_attr="parked_location"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar device trackers."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for description in TRACKERS:
            entities.append(PolestarDeviceTracker(coordinator, description))
    async_add_entities(entities)


class PolestarDeviceTracker(PolestarEntity, TrackerEntity):
    """Polestar GPS device tracker."""

    def __init__(self, coordinator, description: PolestarTrackerDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def location_data(self):
        if self.coordinator.data is None:
            return None
        return getattr(self.coordinator.data, self.entity_description.data_attr)

    @property
    def latitude(self) -> float | None:
        location = self.location_data
        coord = location.coordinate if location else None
        return coord.latitude if coord else None

    @property
    def longitude(self) -> float | None:
        location = self.location_data
        coord = location.coordinate if location else None
        return coord.longitude if coord else None

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        location = self.location_data
        if location is None:
            return {}
        return {
            "heading": location.heading,
            "speed": location.speed,
            "altitude": location.altitude,
        }
