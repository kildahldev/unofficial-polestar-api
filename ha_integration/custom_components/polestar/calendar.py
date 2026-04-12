"""Calendar platform for Polestar parking climate timers."""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta

from dateutil.rrule import DAILY, WEEKLY, rrulestr

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import PolestarCoordinator
from .entity import PolestarEntity
from polestar_api.models.common import Weekday
from polestar_api.models.parking_climate_timer import ParkingClimateTimer
from .utils import serialize_parking_climate_timer

_CALENDAR_SLOTS = (0, 1, 2)
_WEEKDAY_RRULE = {
    Weekday.MONDAY: "MO",
    Weekday.TUESDAY: "TU",
    Weekday.WEDNESDAY: "WE",
    Weekday.THURSDAY: "TH",
    Weekday.FRIDAY: "FR",
    Weekday.SATURDAY: "SA",
    Weekday.SUNDAY: "SU",
}
_RRULE_WEEKDAY = {value: key for key, value in _WEEKDAY_RRULE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar calendar entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for slot in _CALENDAR_SLOTS:
            entities.append(PolestarParkingClimateTimerCalendar(coordinator, slot))
    async_add_entities(entities)


class PolestarParkingClimateTimerCalendar(PolestarEntity, CalendarEntity):
    """Calendar entity representing one parking climate timer slot."""

    def __init__(self, coordinator: PolestarCoordinator, slot: int) -> None:
        super().__init__(coordinator)
        self._slot = slot
        self._attr_name = f"Parking climate timer {slot + 1}"
        self._attr_unique_id = f"{self._vehicle.vin}_parking_climate_timer_{slot + 1}"
        self._attr_supported_features = (
            CalendarEntityFeature.CREATE_EVENT
            | CalendarEntityFeature.UPDATE_EVENT
            | CalendarEntityFeature.DELETE_EVENT
        )

    @property
    def timer(self) -> ParkingClimateTimer | None:
        if self.coordinator.data is None:
            return None
        for timer in self.coordinator.data.climate_timers:
            if timer.index == self._slot:
                return timer
        return None

    @property
    def available(self) -> bool:
        return super().available

    @property
    def event(self) -> CalendarEvent | None:
        window_start = dt_util.now()
        window_end = window_start + timedelta(days=14)
        events = self._build_events(window_start, window_end)
        return events[0] if events else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        timer = self.timer
        if timer is None:
            return {"slot": self._slot + 1}
        return {"slot": self._slot + 1, **serialize_parking_climate_timer(timer)}

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events in the requested range."""
        return self._build_events(start_date, end_date)

    async def async_create_event(self, **kwargs) -> None:
        """Create a parking climate timer in an empty slot."""
        if self.timer is not None:
            raise HomeAssistantError("This parking climate timer slot is already in use")
        timer = self._timer_from_event(kwargs)
        await self.coordinator.async_set_climate_timer(timer)

    async def async_update_event(
        self,
        uid: str,
        event: dict,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Update an existing parking climate timer."""
        if recurrence_id or recurrence_range:
            raise HomeAssistantError("Updating a single recurring timer occurrence is not supported")
        current_timer = self.timer
        if current_timer is None or current_timer.timer_id != uid:
            raise HomeAssistantError("Parking climate timer not found")
        timer = self._timer_from_event(event, current_timer=current_timer)
        await self.coordinator.async_set_climate_timer(timer)

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete a parking climate timer."""
        if recurrence_id or recurrence_range:
            raise HomeAssistantError("Deleting a single recurring timer occurrence is not supported")
        current_timer = self.timer
        if current_timer is None or current_timer.timer_id != uid:
            raise HomeAssistantError("Parking climate timer not found")
        await self.coordinator.async_delete_climate_timer(uid)

    def _build_events(self, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        timer = self.timer
        if timer is None or not timer.activated:
            return []

        timezone = dt_util.DEFAULT_TIME_ZONE
        event_time = dt_time(hour=timer.ready_at_hour, minute=timer.ready_at_minute, tzinfo=timezone)
        weekdays = {day.value - 1 for day in timer.weekdays if day.value > 0}
        rrule = _timer_rrule(timer)

        events: list[CalendarEvent] = []
        current_date = start_date.astimezone(timezone).date()
        last_date = end_date.astimezone(timezone).date()
        while current_date <= last_date:
            if weekdays and current_date.weekday() not in weekdays:
                current_date += timedelta(days=1)
                continue
            event_start = datetime.combine(current_date, event_time)
            if not weekdays and event_start < start_date:
                current_date += timedelta(days=1)
                continue
            if event_start > end_date:
                break
            if event_start >= start_date:
                events.append(
                    CalendarEvent(
                        summary=f"Timer {self._slot + 1}",
                        start=event_start,
                        end=event_start + timedelta(minutes=1),
                        uid=timer.timer_id,
                        rrule=rrule,
                    )
                )
                if not timer.repeat:
                    break
            current_date += timedelta(days=1)
            if not weekdays and not timer.repeat:
                break
        return events

    def _timer_from_event(
        self,
        event: dict,
        *,
        current_timer: ParkingClimateTimer | None = None,
    ) -> ParkingClimateTimer:
        """Convert a HA calendar event payload into a parking climate timer."""
        start_value = _coerce_event_datetime(event.get("start"), "start")
        weekdays, repeat = _parse_weekdays(start_value, event.get("rrule"))
        current_timer = current_timer or self.timer
        return ParkingClimateTimer(
            timer_id="" if current_timer is None else current_timer.timer_id,
            index=self._slot if current_timer is None else current_timer.index,
            ready_at_hour=start_value.hour,
            ready_at_minute=start_value.minute,
            activated=True,
            repeat=repeat,
            weekdays=weekdays,
        )


def _coerce_event_datetime(value: object, field_name: str) -> datetime:
    """Validate and normalize a HA calendar datetime payload."""
    if not isinstance(value, datetime):
        raise HomeAssistantError(f"{field_name} must be a date-time for Polestar parking climate timers")
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt_util.as_local(value)


def _parse_weekdays(start: datetime, rrule: str | None) -> tuple[tuple[Weekday, ...], bool]:
    """Convert a HA recurrence rule into Polestar timer weekdays."""
    if not rrule:
        return ((_weekday_from_python(start.weekday()),), False)

    rule = rrulestr(rrule, dtstart=start)
    if getattr(rule, "_interval", 1) != 1:
        raise HomeAssistantError("Only interval=1 recurrence rules are supported for Polestar timers")
    if getattr(rule, "_until", None) is not None:
        raise HomeAssistantError("Recurrence rules with an end date are not supported for Polestar timers")

    count = getattr(rule, "_count", None)
    if count == 1:
        return ((_weekday_from_python(start.weekday()),), False)
    if count not in (None, 0):
        raise HomeAssistantError("Finite recurring timer series are not supported for Polestar timers")

    if rule._freq == DAILY:
        return (
            (
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
                Weekday.THURSDAY,
                Weekday.FRIDAY,
                Weekday.SATURDAY,
                Weekday.SUNDAY,
            ),
            True,
        )

    if rule._freq != WEEKLY:
        raise HomeAssistantError("Only daily or weekly recurrence rules are supported for Polestar timers")

    byweekday = getattr(rule, "_byweekday", None) or (_python_weekday_rrule(start.weekday()),)
    weekdays: list[Weekday] = []
    for item in byweekday:
        weekday = _weekday_from_rrule_item(item)
        if weekday not in weekdays:
            weekdays.append(weekday)
    return (tuple(weekdays), True)


def _weekday_from_python(value: int) -> Weekday:
    """Convert Python weekday numbering to the Polestar enum."""
    return Weekday(value + 1)


def _weekday_from_rrule_item(value: object) -> Weekday:
    """Convert a dateutil RRULE weekday item into a Polestar enum."""
    if isinstance(value, int):
        return _weekday_from_python(value)

    weekday_index = getattr(value, "weekday", None)
    if isinstance(weekday_index, int):
        return _weekday_from_python(weekday_index)

    if isinstance(value, str):
        weekday = _RRULE_WEEKDAY.get(value[:2].upper())
        if weekday is not None:
            return weekday

    weekday = _RRULE_WEEKDAY.get(str(value)[:2].upper())
    if weekday is not None:
        return weekday

    raise HomeAssistantError(f"Unsupported recurrence weekday: {value}")


def _python_weekday_rrule(value: int) -> str:
    """Convert a Python weekday to an RRULE weekday code."""
    return _WEEKDAY_RRULE[_weekday_from_python(value)]


def _timer_rrule(timer: ParkingClimateTimer) -> str | None:
    """Convert a parking climate timer to an RRULE for HA editing."""
    if not timer.repeat:
        return None
    weekdays = [code for day, code in _WEEKDAY_RRULE.items() if day in timer.weekdays]
    if not weekdays:
        return "FREQ=DAILY"
    return f"FREQ=WEEKLY;BYDAY={','.join(weekdays)}"
