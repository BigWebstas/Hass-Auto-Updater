"""Button to start an update check/install run on demand."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _run_update_job
from .const import DATA_STATUS, DOMAIN, STATUS_RUNNING


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([RunUpdatesNowButton(entry)])


class RunUpdatesNowButton(ButtonEntity):
    """Runs the update job immediately, overriding the schedule.

    This is an explicit override: it ignores both the pause switch and the
    reboot window, so pressing it installs pending updates and restarts Home
    Assistant right now, whatever the schedule says. Because it can restart HA
    at any hour, use it deliberately.
    """

    _attr_name = "Run Updates Now"
    _attr_icon = "mdi:play-circle"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_run_now"

    @property
    def available(self) -> bool:
        """Disable the button while a run is already in progress."""
        store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return store.get(DATA_STATUS) != STATUS_RUNNING

    async def async_press(self) -> None:
        """Start an overriding run in the background so the press returns immediately."""
        self._entry.async_create_background_task(
            self.hass,
            _run_update_job(self.hass, self._entry, force=True),
            "hass_auto_updater_manual_run",
        )
