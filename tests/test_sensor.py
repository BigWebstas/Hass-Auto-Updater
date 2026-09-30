"""Tests for the status sensor, including persistence across a restart."""

from __future__ import annotations

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update import SERVICE_INSTALL
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.hass_auto_updater import _run_update_job
from custom_components.hass_auto_updater.const import (
    CONF_REBOOT_WINDOW,
    DATA_ENABLED,
    STATUS_DEFERRED,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
)

from .conftest import (
    ADDON,
    ADDON_2,
    SENSOR,
    WINDOW,
    make_entry,
    set_state,
    setup_integration,
    store_for,
)


def attributes(hass: HomeAssistant) -> dict:
    """Return the status sensor's attributes."""
    return dict(hass.states.get(SENSOR).attributes)


async def test_initial_state_is_idle(hass: HomeAssistant) -> None:
    """The sensor starts idle with a full set of attributes."""
    await setup_integration(hass, make_entry())

    assert hass.states.get(SENSOR).state == STATUS_IDLE
    attrs = attributes(hass)
    assert attrs["enabled"] is True
    assert attrs["pending_updates"] == 0
    assert attrs["current_update"] is None
    assert attrs["last_run"] is None
    assert attrs["last_installed"] == []
    assert attrs["last_errors"] == []


async def test_paused_reflects_switch(hass: HomeAssistant) -> None:
    """Turning the switch off reports paused."""
    await setup_integration(hass, make_entry())

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.auto_updater_enabled"}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR).state == STATUS_PAUSED
    assert attributes(hass)["enabled"] is False


async def test_unpausing_does_not_leave_stale_paused(hass: HomeAssistant) -> None:
    """Turning the switch back on restores the real status, not `paused`."""
    await setup_integration(hass, make_entry())
    switch = "switch.auto_updater_enabled"

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == STATUS_PAUSED

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR).state == STATUS_IDLE


async def test_deferred_status(hass: HomeAssistant, services) -> None:
    """A run outside the window reports deferred and keeps the pending count."""
    entry = await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert hass.states.get(SENSOR).state == STATUS_DEFERRED
    assert attributes(hass)["pending_updates"] == 1


async def test_current_update_and_countdown(hass: HomeAssistant, services) -> None:
    """`current_update` and `pending_updates` track the run."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")
    set_state(hass, ADDON_2, "on")

    seen: list[tuple] = []

    async def _capture(call: ServiceCall) -> None:
        attrs = attributes(hass)
        seen.append((attrs["current_update"], attrs["pending_updates"]))
        services.installed.extend(call.data["entity_id"])

    hass.services.async_register(UPDATE_DOMAIN, SERVICE_INSTALL, _capture)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert seen == [(ADDON, 2), (ADDON_2, 1)]
    assert attributes(hass)["current_update"] is None
    assert attributes(hass)["pending_updates"] == 0


async def test_last_run_details_recorded(hass: HomeAssistant, services) -> None:
    """A completed run is reflected in the sensor attributes."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")
    set_state(hass, ADDON_2, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    attrs = attributes(hass)
    assert attrs["last_installed"] == [ADDON]
    assert attrs["last_run"] is not None
    assert hass.states.get(SENSOR).state == STATUS_IDLE


async def test_forced_run_while_paused_reports_running(hass: HomeAssistant, services) -> None:
    """A forced run reports running even though the switch is off."""
    entry = await setup_integration(hass, make_entry())
    store_for(hass, entry)[DATA_ENABLED] = False
    set_state(hass, ADDON, "on")

    observed: list[str] = []

    async def _capture(call: ServiceCall) -> None:
        observed.append(hass.states.get(SENSOR).state)
        services.installed.extend(call.data["entity_id"])

    hass.services.async_register(UPDATE_DOMAIN, SERVICE_INSTALL, _capture)

    await _run_update_job(hass, entry, force=True)
    await hass.async_block_till_done()

    assert observed == [STATUS_RUNNING]
    # Back to paused once the forced run finishes.
    assert hass.states.get(SENSOR).state == STATUS_PAUSED


async def test_last_run_details_survive_restart(hass: HomeAssistant, services) -> None:
    """Unload and reload the entry; the last-run details are still there.

    This is the persistence guarantee: an HA restart rebuilds the integration
    from scratch, and `last_run` / `last_installed` / `last_errors` come back.
    """
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")
    set_state(hass, ADDON_2, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()
    before = attributes(hass)
    assert before["last_installed"] == [ADDON]

    # Simulate a restart: tear the entry down and set it up again.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # HA leaves a restored/unavailable placeholder behind, which is expected for
    # a RestoreEntity once the platform is unloaded.
    assert hass.states.get(SENSOR).state == "unavailable"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    after = attributes(hass)
    assert after["last_installed"] == [ADDON]
    assert after["last_run"] == before["last_run"]
    assert after["last_errors"] == before["last_errors"]
    # Transient run state is not carried over.
    assert after["pending_updates"] == 0
    assert after["current_update"] is None
    assert hass.states.get(SENSOR).state == STATUS_IDLE


async def test_errors_survive_restart(hass: HomeAssistant, services) -> None:
    """Failed installs are also restored."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")
    services.failing.add(ADDON)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()
    assert attributes(hass)["last_errors"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert attributes(hass)["last_errors"]


async def test_fresh_install_has_no_history(hass: HomeAssistant) -> None:
    """A first-time install reports no previous run."""
    await setup_integration(hass, make_entry())

    attrs = attributes(hass)
    assert attrs["last_run"] is None
    assert attrs["last_installed"] == []
