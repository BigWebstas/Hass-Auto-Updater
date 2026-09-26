"""Auto Updater: installs pending updates on a schedule and restarts Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_DAY,
    CONF_TIME,
    DATA_ENABLED,
    DAY_DAILY,
    DEFAULT_TIME,
    DOMAIN,
    INSTALL_LAST_PREFIXES,
    PLATFORMS,
    WEEKDAY_INDEX,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_ENABLED: True}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    day = entry.data.get(CONF_DAY, DAY_DAILY)
    hour, minute, second = (int(part) for part in entry.data.get(CONF_TIME, DEFAULT_TIME).split(":"))

    async def _scheduled_run(now) -> None:
        if day != DAY_DAILY and now.weekday() != WEEKDAY_INDEX.get(day):
            return
        await _run_update_job(hass, entry)

    remove_listener = async_track_time_change(hass, _scheduled_run, hour=hour, minute=minute, second=second)
    entry.async_on_unload(remove_listener)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _install_sort_key(entity_id: str) -> int:
    return 1 if entity_id.startswith(INSTALL_LAST_PREFIXES) else 0


async def _run_update_job(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Install any pending updates, then restart Home Assistant if anything installed."""
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not store or not store.get(DATA_ENABLED, True):
        _LOGGER.debug("Auto updater is paused, skipping scheduled run")
        return

    pending = sorted(
        (state.entity_id for state in hass.states.async_all("update") if state.state == "on"),
        key=_install_sort_key,
    )
    if not pending:
        _LOGGER.debug("Auto updater found no pending updates")
        return

    updated_any = False
    for entity_id in pending:
        _LOGGER.info("Auto updater installing update for %s", entity_id)
        try:
            await hass.services.async_call(
                "update", "install", {"entity_id": entity_id}, blocking=True
            )
            updated_any = True
        except Exception as err:  # noqa: BLE001 - one failing entity must not stop the rest
            _LOGGER.error("Auto updater failed installing update for %s: %s", entity_id, err)

    if updated_any:
        _LOGGER.warning("Auto updater installed updates, restarting Home Assistant")
        await hass.services.async_call("homeassistant", "restart", {}, blocking=False)
