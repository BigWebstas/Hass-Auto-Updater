"""Auto Updater: installs pending updates on a schedule and restarts Home Assistant."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)

from .const import (
    ADDON_UPDATE_PREFIX,
    CONF_DAY,
    CONF_FREQUENCY,
    CONF_REBOOT_WINDOW,
    CONF_TIME,
    DATA_ENABLED,
    DATA_RUN_PENDING,
    DAY_DAILY,
    DEFAULT_TIME,
    DOMAIN,
    FREQUENCY_INTERVALS,
    FREQUENCY_SCHEDULED,
    INSTALL_LAST_PREFIXES,
    PLATFORMS,
    WEEKDAY_INDEX,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {DATA_ENABLED: True}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    frequency = entry.data.get(CONF_FREQUENCY, FREQUENCY_SCHEDULED)
    if frequency == FREQUENCY_SCHEDULED:
        remove_listener = _schedule_at_day_and_time(hass, entry)
    else:
        remove_listener = _schedule_on_interval(hass, entry, frequency)

    entry.async_on_unload(remove_listener)

    if reboot_window := entry.data.get(CONF_REBOOT_WINDOW):
        entry.async_on_unload(_run_deferred_when_window_opens(hass, entry, reboot_window))
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


def _schedule_at_day_and_time(hass: HomeAssistant, entry: ConfigEntry):
    day = entry.data.get(CONF_DAY, DAY_DAILY)
    hour, minute, second = (int(part) for part in entry.data.get(CONF_TIME, DEFAULT_TIME).split(":"))

    async def _run(now) -> None:
        if day != DAY_DAILY and now.weekday() != WEEKDAY_INDEX.get(day):
            return
        await _run_update_job(hass, entry)

    return async_track_time_change(hass, _run, hour=hour, minute=minute, second=second)


def _schedule_on_interval(hass: HomeAssistant, entry: ConfigEntry, frequency: str):
    async def _run(now) -> None:
        await _run_update_job(hass, entry)

    hours = FREQUENCY_INTERVALS.get(frequency, FREQUENCY_INTERVALS["hourly"])
    return async_track_time_interval(hass, _run, timedelta(hours=hours))


def _run_deferred_when_window_opens(hass: HomeAssistant, entry: ConfigEntry, reboot_window: str):
    @callback
    def _window_changed(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None or new_state.state != STATE_ON:
            return
        store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if store and store.pop(DATA_RUN_PENDING, False):
            _LOGGER.info("Reboot window %s opened, running deferred update job", reboot_window)
            entry.async_create_background_task(
                hass, _run_update_job(hass, entry), "hass_auto_updater_deferred_run"
            )

    return async_track_state_change_event(hass, [reboot_window], _window_changed)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _install_sort_key(entity_id: str) -> int:
    """Sort add-ons first, core/supervisor/OS last."""
    return 1 if entity_id.startswith(INSTALL_LAST_PREFIXES) else 0


def _is_addon_update(entity_id: str) -> bool:
    """Return True if the entity is an add-on update (not core/supervisor/OS)."""
    return entity_id.startswith(ADDON_UPDATE_PREFIX) and not entity_id.startswith(INSTALL_LAST_PREFIXES)


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

    # Installing core/add-on updates and the final restart all interrupt HA,
    # so the whole run waits for the reboot window rather than just the restart.
    reboot_window = entry.data.get(CONF_REBOOT_WINDOW)
    if reboot_window:
        window_state = hass.states.get(reboot_window)
        if window_state is None or window_state.state != STATE_ON:
            # A missing window entity also defers: never restart outside the user's window.
            _LOGGER.info("Outside reboot window %s, deferring updates until it turns on", reboot_window)
            store[DATA_RUN_PENDING] = True
            return

    updated_any = False
    for entity_id in pending:
        update_type = "add-on" if _is_addon_update(entity_id) else "core"
        _LOGGER.info("Auto updater installing %s update for %s", update_type, entity_id)
        try:
            await hass.services.async_call(
                "update", "install", {"entity_id": entity_id}, blocking=True
            )
            updated_any = True
        except Exception as err:  # noqa: BLE001 - one failing entity must not stop the rest
            _LOGGER.error("Auto updater failed installing %s update for %s: %s", update_type, entity_id, err)

    if updated_any:
        _LOGGER.warning("Auto updater installed updates, restarting Home Assistant")
        await hass.services.async_call("homeassistant", "restart", {}, blocking=False)
