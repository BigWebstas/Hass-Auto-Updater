"""Shared fixtures and constants for the Auto Updater integration tests."""

from __future__ import annotations

import pytest
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update import SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_auto_updater.const import CONF_FREQUENCY, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

# Entity ids used across the suite.
ADDON = "update.mosquitto"
ADDON_2 = "update.node_red"
CORE = "update.home_assistant_core"
SUPERVISOR = "update.home_assistant_supervisor"
WINDOW = "schedule.night"

SENSOR = "sensor.auto_updater_status"
SWITCH = "switch.auto_updater_enabled"
BUTTON = "button.auto_updater_run_now"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow the custom integration to be loaded in tests."""
    yield


@pytest.fixture
def services(hass: HomeAssistant):
    """Register real `update.install` / `homeassistant.restart` handlers.

    The integration runs its normal code path against these; only the side
    effects are recorded, so tests can assert on what was installed and whether
    a restart was requested. Real HA is used throughout, so the entities under
    test are the integration's own.
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
        """Simple namespace holding the recorded calls."""

    recorder = Recorder()
    recorder.installed = installed
    recorder.restarted = restarted
    recorder.failing = failing
    return recorder


def make_entry(**data) -> MockConfigEntry:
    """Build a config entry, defaulting to the hourly frequency."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_FREQUENCY: "hourly", **data},
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Register and set up a config entry, then wait for it to finish loading."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def set_state(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Set an entity state directly (no underlying integration needed)."""
    hass.states.async_set(entity_id, state)


def store_for(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    """Return the integration's runtime store for an entry."""
    return hass.data[DOMAIN][entry.entry_id]
