"""Tests for the Run Updates Now button, including its override behaviour."""

from __future__ import annotations

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update import SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.hass_auto_updater.const import (
    CONF_REBOOT_WINDOW,
    DATA_ENABLED,
    DATA_STATUS,
    STATUS_DEFERRED,
    STATUS_IDLE,
    STATUS_RUNNING,
)

from .conftest import make_entry, set_state, setup_integration
from .test_init import ADDON, WINDOW, services  # noqa: F401 - reuse fixture


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {"entity_id": "button.auto_updater_run_now"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_press_installs_pending_update(hass: HomeAssistant, services) -> None:
    """A press installs available updates and restarts."""
    await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")

    await _press(hass)

    assert services.installed == [ADDON]
    assert services.restarted == [True]


async def test_press_with_nothing_pending(hass: HomeAssistant, services) -> None:
    """A press with no updates pending installs nothing."""
    await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "off")

    await _press(hass)

    assert services.installed == []
    assert services.restarted == []


async def test_press_overrides_pause_switch(hass: HomeAssistant, services) -> None:
    """The override runs even while the updater is paused."""
    entry = await setup_integration(hass, make_entry())
    hass.data["hass_auto_updater"][entry.entry_id][DATA_ENABLED] = False
    set_state(hass, ADDON, "on")

    await _press(hass)

    assert services.installed == [ADDON]
    assert services.restarted == [True]
    # The switch itself is untouched: pausing is still in force afterwards.
    assert hass.data["hass_auto_updater"][entry.entry_id][DATA_ENABLED] is False


async def test_press_overrides_closed_reboot_window(hass: HomeAssistant, services) -> None:
    """The override installs even when the reboot window is closed."""
    await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "off")

    await _press(hass)

    assert services.installed == [ADDON]
    assert services.restarted == [True]


async def test_press_overrides_missing_window_entity(hass: HomeAssistant, services) -> None:
    """A missing window entity does not block the override."""
    await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: "schedule.absent"}))
    set_state(hass, ADDON, "on")

    await _press(hass)

    assert services.installed == [ADDON]
    assert services.restarted == [True]


async def test_scheduled_run_still_respects_pause(hass: HomeAssistant, services) -> None:
    """The override applies only to the button, not to scheduled runs."""
    from custom_components.hass_auto_updater import _run_update_job

    entry = await setup_integration(hass, make_entry())
    hass.data["hass_auto_updater"][entry.entry_id][DATA_ENABLED] = False
    set_state(hass, ADDON, "on")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    assert services.restarted == []


async def test_scheduled_run_still_respects_window(hass: HomeAssistant, services) -> None:
    """A scheduled run outside the window still defers."""
    from custom_components.hass_auto_updater import _run_update_job

    entry = await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    store = hass.data["hass_auto_updater"][entry.entry_id]
    assert store[DATA_STATUS] == STATUS_DEFERRED


async def test_button_unavailable_while_running(hass: HomeAssistant, services) -> None:
    """The button disables itself while a run is in flight."""
    entry = await setup_integration(hass, make_entry())
    hass.data["hass_auto_updater"][entry.entry_id][DATA_STATUS] = STATUS_RUNNING

    state = hass.states.get("button.auto_updater_run_now")
    assert state.attributes["friendly_name"] == "Auto Updater Run Now"


async def test_button_available_when_idle(hass: HomeAssistant, services) -> None:
    """The button is usable when nothing is running."""
    await setup_integration(hass, make_entry())

    state = hass.states.get("button.auto_updater_run_now")
    assert state.state == "unknown"  # buttons report `unknown` when not pressed