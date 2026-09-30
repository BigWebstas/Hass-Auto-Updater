"""Tests for the pause/resume switch."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.hass_auto_updater.const import DATA_ENABLED

from .conftest import SWITCH, make_entry, setup_integration, store_for


async def test_switch_starts_on(hass: HomeAssistant) -> None:
    """The switch defaults to on."""
    entry = await setup_integration(hass, make_entry())

    assert hass.states.get(SWITCH).state == "on"
    assert store_for(hass, entry)[DATA_ENABLED] is True


async def test_turn_off_updates_store(hass: HomeAssistant) -> None:
    """Turning the switch off updates the run store."""
    entry = await setup_integration(hass, make_entry())

    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH).state == "off"
    assert store_for(hass, entry)[DATA_ENABLED] is False


async def test_turn_on_updates_store(hass: HomeAssistant) -> None:
    """Turning the switch back on updates the run store."""
    entry = await setup_integration(hass, make_entry())

    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH).state == "on"
    assert store_for(hass, entry)[DATA_ENABLED] is True


async def test_switch_state_survives_restart(hass: HomeAssistant) -> None:
    """The pause state is restored, so a restart does not silently resume."""
    entry = await setup_integration(hass, make_entry())

    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH).state == "off"
    assert store_for(hass, entry)[DATA_ENABLED] is False
