"""Time platform for Polestar charge timer controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PolestarCoordinator
from .entity import PolestarEntity
from .utils import minutes_to_time


@dataclass(frozen=True, kw_only=True)
class PolestarTimeDescription(TimeEntityDescription):
    """Time description for global charge timer controls."""

    value_attr: str


TIMES: tuple[PolestarTimeDescription, ...] = (
    PolestarTimeDescription(
        key="charge_timer_start",
        name="Charge timer start",
        icon="mdi:clock-start",
        entity_category=EntityCategory.CONFIG,
        value_attr="start",
    ),
    PolestarTimeDescription(
        key="charge_timer_stop",
        name="Charge timer stop",
        icon="mdi:clock-end",
        entity_category=EntityCategory.CONFIG,
        value_attr="stop",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar time entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for description in TIMES:
            entities.append(PolestarChargeTimerTime(coordinator, description))
    async_add_entities(entities)


class PolestarChargeTimerTime(PolestarEntity, TimeEntity):
    """Time entity for charge timer start/stop configuration."""

    entity_description: PolestarTimeDescription

    def __init__(self, coordinator: PolestarCoordinator, description: PolestarTimeDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.charge_timer is not None
            and self.coordinator.data.charge_timer.timer is not None
        )

    @property
    def native_value(self) -> dt_time | None:
        if not self.available:
            return None
        timer = self.coordinator.data.charge_timer.timer
        return minutes_to_time(getattr(timer, self.entity_description.value_attr))

    async def async_set_value(self, value: dt_time) -> None:
        kwargs = {"start": value} if self.entity_description.value_attr == "start" else {"stop": value}
        await self.coordinator.async_set_charge_timer(**kwargs)
