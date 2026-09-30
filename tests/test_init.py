"""Tests for the core install logic."""

from __future__ import annotations

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update import SERVICE_INSTALL
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

from .conftest import (
    ADDON,
    ADDON_2,
    BUTTON,
    CORE,
    SENSOR,
    SUPERVISOR,
    WINDOW,
    make_entry,
    set_state,
    setup_integration,
    store_for,
)


async def test_entities_are_created(hass: HomeAssistant) -> None:
    """All three entities are created with the documented entity_ids."""
    await setup_integration(hass, make_entry())

    assert hass.states.get("switch.auto_updater_enabled").state == "on"
    assert hass.states.get(SENSOR).state == STATUS_IDLE
    assert hass.states.get(BUTTON) is not None


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

    store = store_for(hass, entry)
    assert store[DATA_LAST_INSTALLED] == [ADDON]
    assert store[DATA_LAST_ERRORS] == []
    assert store[DATA_STATUS] == STATUS_IDLE


async def test_failed_install_is_recorded_and_run_continues(hass: HomeAssistant, services) -> None:
    """One failing entity does not stop the rest, and is reported."""
    entry = await setup_integration(hass, make_entry())
    for entity_id in (ADDON, ADDON_2):
        set_state(hass, entity_id, "on")
    services.failing.add(ADDON)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    store = store_for(hass, entry)
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
    assert store_for(hass, entry)[DATA_STATUS] == STATUS_IDLE


async def test_closed_window_defers(hass: HomeAssistant, services) -> None:
    """Outside the reboot window the run defers instead of installing."""
    entry = await setup_integration(hass, make_entry(**{CONF_REBOOT_WINDOW: WINDOW}))
    set_state(hass, ADDON, "on")
    set_state(hass, WINDOW, "off")

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert services.installed == []
    assert services.restarted == []
    store = store_for(hass, entry)
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
        observed.append(hass.states.get(SENSOR).state)
        services.installed.extend(call.data["entity_id"])

    hass.services.async_register(UPDATE_DOMAIN, SERVICE_INSTALL, _slow_install)

    await _run_update_job(hass, entry)
    await hass.async_block_till_done()

    assert observed == [STATUS_RUNNING]
    assert hass.states.get(SENSOR).state == STATUS_IDLE
