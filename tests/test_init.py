"""Tests for the core install logic and scheduling."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update import SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.hass_auto_updater import _run_update_job
from custom_components.hass_auto_updater.const import (
    CONF_REBOOT_WINDOW,
    DATA_LAST_ERRORS,
    DATA_LAST_INSTALLED,
    DATA_STATUS,
    STATUS_DEFERRED,
    STATUS_IDLE,
    STATUS_RUNNING,
)

from .conftest import make_entry, set_state, setup_integration

ADDON = "update.mosquitto"
ADDON_2 = "update.node_red"
CORE = "update.home_assistant_core"
SUPERVISOR = "update.home_assistant_supervisor"
WINDOW = "schedule.night"


@pytest.fixture
def services(hass: HomeAssistant):
    """Register real service handlers and record what the integration calls.

    `update.install` and `homeassistant.restart` are registered for real so the
    integration runs its normal code path; only the side effects are recorded.
    """
    installed: list[str] = []
    restarted: list[bool] = []
    failing: set[str] = set()

    async def _handle_install(call: ServiceCall) -> None:
        entity_ids = call.data.get(ATTR_ENTITY_ID)
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        for entity_id in entity_ids:
            if entity_id in failing:
                raise RuntimeError(f"install failed: {entity_id}")
            installed.append(entity_id)

    async def _handle_restart(call: ServiceCall) -> None:
        restarted.append(True)

    hass.services.async_register(UPDATE_DOMAIN, SERVICE_INSTALL, _handle_install)
    hass.services.async_register("homeassistant", "restart", _handle_restart)

    class Recorder:
        pass

    rec = Recorder()
    rec.installed = installed
    rec.restarted = restarted
    rec.failing = failing
    return rec


async def test_entities_are_created(hass: HomeAssistant) -> None:
    """All three entities are created with the documented entity_ids."""
    await setup_integration(hass, make_entry())

    assert hass.states.get("switch.auto_updater_enabled").state == "on"
    assert hass.states.get("sensor.auto_updater_status").state == STATUS_IDLE
    assert hass.states.get("button.auto_updater_run_now") is not None


async def test_no_pending_updates_does_nothing(hass: HomeAssistant, services) -> None:
    """A run with nothing pending installs nothing and does not restart."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    assert services.restarted == []


async def test_installs_addons_before_core(hass: HomeAssistant, services) -> None:
    """Add-ons install first; core and supervisor go last."""
    entry = await setup_integration(hass, make_entry())
    for entity_id in (CORE, ADDON, SUPERVISOR, ADDON_2):
        set_state(hass, entity_id, "on")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed.index(ADDON) < services.installed.index(CORE)
    assert services.installed.index(ADDON_2) < services.installed.index(CORE)
    assert services.installed[-1] == SUPERVISOR
    assert services.restarted == [True]


async def test_records_last_installed(hass: HomeAssistant, services) -> None:
    """A successful run is recorded for the status sensor."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")
    set_state(hass, ADDON_2, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    store = hass.data["hass_auto_updater"][entry.entry_id]
    assert store[DATA_LAST_INSTALLED] == [ADDON]
    assert store[DATA_LAST_ERRORS] == []
    assert store[DATA_STATUS] == STATUS_IDLE


async def test_failed_install_is_recorded_and_run_continues(
    hass: HomeAssistant, services
) -> None:
    """One failing entity does not stop the rest, and is reported."""
    entry = await setup_integration(hass, make_entry())
    for entity_id in (ADDON, ADDON_2):
        set_state(hass, entity_id, "on")
    services.failing.add(ADDON)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    store = hass.data["hass_auto_updater"][entry.entry_id]
    assert ADDON not in services.installed
    assert ADDON_2 in services.installed
    assert any(ADDON in err for err in store[DATA_LAST_ERRORS])
    # A partial success still restarts.
    assert services.restarted == [True]


async def test_all_failing_does_not_restart(hass: HomeAssistant, services) -> None:
    """If nothing installed, HA is not restarted."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")
    services.failing.add(ADDON)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    assert services.restarted == []
    store = hass.data["hass_auto_updater"][entry.entry_id]
    assert store[DATA_STATUS] == STATUS_IDLE


async def test_closed_window_defers(hass: HomeAssistant, services) -> None:
    """Outside the reboot window the run defers instead of installing."""
    entry = await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    assert services.restarted == []
    store = hass.data["hass_auto_updater"][entry.entry_id]
    assert store[DATA_STATUS] == STATUS_DEFERRED
    assert store["run_pending"] is True


async def test_open_window_installs(hass: HomeAssistant, services) -> None:
    """Inside the reboot window the run proceeds."""
    entry = await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "on")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == [ADDON]
    assert services.restarted == [True]


async def test_deferred_run_fires_when_window_opens(hass: HomeAssistant, services) -> None:
    """A deferred run executes once the reboot window turns on."""
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    entry = await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()
    assert services.installed == []

    set_state(hass, WINDOW, "on")
    await hass.async_block_till_done()

    assert services.installed == [ADDON]
    assert services.restarted == [True]


async def test_paused_run_does_nothing(hass: HomeAssistant, services) -> None:
    """The pause switch blocks scheduled runs."""
    entry = await setup_integration(hass, make_entry())
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.auto_updater_enabled"}, blocking=True
    )
    await hass.async_block_till_done()
    set_state(hass, ADDON, "on")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    assert services.restarted == []


async def test_status_is_running_during_run(hass: HomeAssistant, services) -> None:
    """The sensor reports `running` while installs are in flight."""
    entry = await setup_integration(hass, make_entry())
    set_state(hass, ADDON, "on")

    observed: list[str] = []

    async def _slow_install(call: ServiceCall) -> None:
        observed.append(hass.states.get("sensor.auto_updater_status").state)
        services.installed.append(ADDON)

    hass.services.async_register(UPDATE_DOMAIN, SERVICE_INSTALL, _slow_install)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert observed == [STATUS_RUNNING]
    assert hass.states.get("sensor.auto_updater_status").state == STATUS_IDLE