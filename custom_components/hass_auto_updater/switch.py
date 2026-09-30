"""Pause/resume switch for the Auto Updater integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATA_ENABLED, DOMAIN, SIGNAL_STATUS_UPDATED


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([AutoUpdaterEnabledSwitch(entry)])


class AutoUpdaterEnabledSwitch(SwitchEntity, RestoreEntity):
    """When off, the scheduled update job skips its run."""

    _attr_name = "Auto Updater Enabled"
    _attr_icon = "mdi:update"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        self._sync_store()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self._sync_store()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self._sync_store()
        self.async_write_ha_state()

    def _sync_store(self) -> None:
        store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        if store is not None:
            store[DATA_ENABLED] = self._attr_is_on
            # Keep the status sensor in step with the pause switch.
            async_dispatcher_send(self.hass, SIGNAL_STATUS_UPDATED, self._entry.entry_id)
