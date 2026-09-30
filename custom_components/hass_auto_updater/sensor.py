"""Status sensor for the Auto Updater integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_CURRENT_ENTITY,
    DATA_ENABLED,
    DATA_LAST_ERRORS,
    DATA_LAST_INSTALLED,
    DATA_LAST_RUN,
    DATA_PENDING_COUNT,
    DATA_STATUS,
    DOMAIN,
    SIGNAL_STATUS_UPDATED,
    STATUS_IDLE,
    STATUS_PAUSED,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([AutoUpdaterStatusSensor(entry)])


class AutoUpdaterStatusSensor(SensorEntity):
    """Reports what the auto updater is doing right now."""

    _attr_name = "Auto Updater Status"
    _attr_icon = "mdi:update"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_native_value = STATUS_IDLE
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STATUS_UPDATED, self._handle_status_changed
            )
        )

    @callback
    def _handle_status_changed(self, entry_id: str) -> None:
        if entry_id == self._entry.entry_id:
            self._refresh()

    @callback
    def _refresh(self) -> None:
        store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        enabled = store.get(DATA_ENABLED, True)
        # Paused is derived, not stored: the switch can flip it without a run starting.
        self._attr_native_value = store.get(DATA_STATUS, STATUS_IDLE) if enabled else STATUS_PAUSED
        self._attr_extra_state_attributes = {
            "enabled": enabled,
            "pending_updates": store.get(DATA_PENDING_COUNT, 0),
            "current_update": store.get(DATA_CURRENT_ENTITY),
            "last_run": store.get(DATA_LAST_RUN),
            "last_installed": store.get(DATA_LAST_INSTALLED, []),
            "last_errors": store.get(DATA_LAST_ERRORS, []),
        }
        self.async_write_ha_state()
