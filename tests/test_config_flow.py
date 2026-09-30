"""Tests for the config flow."""

from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.hass_auto_updater.const import (
    CONF_DAY,
    CONF_FREQUENCY,
    CONF_REBOOT_WINDOW,
    CONF_TIME,
    DOMAIN,
)

from .conftest import make_entry


async def test_scheduled_flow(hass: HomeAssistant) -> None:
    """Choosing a specific day and time asks for the day/time step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FREQUENCY: "scheduled"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "schedule"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DAY: "monday", CONF_TIME: "04:30:00"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DAY] == "monday"
    assert result["data"][CONF_TIME] == "04:30:00"


async def test_interval_flow_single_step(hass: HomeAssistant) -> None:
    """An interval frequency creates the entry in one step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FREQUENCY: "every_6_hours"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FREQUENCY] == "every_6_hours"


async def test_flow_with_reboot_window(hass: HomeAssistant) -> None:
    """A reboot window can be chosen in the same step."""
    hass.states.async_set("schedule.night", "on")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FREQUENCY: "hourly", CONF_REBOOT_WINDOW: "schedule.night"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REBOOT_WINDOW] == "schedule.night"


async def test_reconfigure_changes_frequency(hass: HomeAssistant) -> None:
    """Reconfigure updates an existing entry and reloads it."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FREQUENCY: "every_12_hours"}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_FREQUENCY] == "every_12_hours"


async def test_reconfigure_to_scheduled_asks_for_day_and_time(hass: HomeAssistant) -> None:
    """Switching an interval entry to a specific day/time asks for the second step."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FREQUENCY: "scheduled"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure_schedule"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DAY: "friday", CONF_TIME: "05:15:00"}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_FREQUENCY] == "scheduled"
    assert entry.data[CONF_DAY] == "friday"
    assert entry.data[CONF_TIME] == "05:15:00"
