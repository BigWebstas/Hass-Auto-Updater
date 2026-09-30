"""Shared fixtures for the Auto Updater integration tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hass_auto_updater.const import CONF_FREQUENCY, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow the custom integration to be loaded in tests."""
    yield


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