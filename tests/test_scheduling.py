"""Tests for the time-based triggers (specific day/time and fixed intervals)."""

from __future__ import annotations

import datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.hass_auto_updater.const import (
    CONF_DAY,
    CONF_FREQUENCY,
    CONF_TIME,
    DATA_LAST_INSTALLED,
)

from .conftest import ADDON, make_entry, set_state, setup_integration, store_for

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


async def test_scheduled_run_fires_at_configured_time(
    hass: HomeAssistant, services, freezer: FrozenDateTimeFactory
) -> None:
    """A daily entry runs when its configured time arrives."""
    # async_track_time_change matches on the *local* wall-clock minute, and the
    # test instance runs in US/Pacific, so build the trigger from local time.
    base = dt_util.now().replace(hour=2, minute=0, second=0, microsecond=0)
    freezer.move_to(base)

    entry = make_entry(**{CONF_FREQUENCY: "scheduled", CONF_DAY: "daily", CONF_TIME: "03:00:00"})
    await setup_integration(hass, entry)
    set_state(hass, ADDON, "on")

    # Before the trigger: nothing should happen.
    async_fire_time_changed(hass, base + datetime.timedelta(minutes=30))
    await hass.async_block_till_done()
    assert services.installed == []

    # Crossing the trigger minute runs it.
    async_fire_time_changed(hass, base + datetime.timedelta(hours=1))
    await hass.async_block_till_done()
    assert services.installed == [ADDON]


async def test_scheduled_run_respects_day_of_week(
    hass: HomeAssistant, services, freezer: FrozenDateTimeFactory
) -> None:
    """An entry pinned to one weekday ignores other days."""
    trigger = dt_util.now().replace(hour=3, minute=0, second=0, microsecond=0)
    freezer.move_to(trigger)
    # Pick a weekday that is definitely not today.
    other_day = WEEKDAYS[(trigger.weekday() + 1) % 7]

    entry = make_entry(**{CONF_FREQUENCY: "scheduled", CONF_DAY: other_day, CONF_TIME: "03:00:00"})
    await setup_integration(hass, entry)
    set_state(hass, ADDON, "on")

    async_fire_time_changed(hass, trigger)
    await hass.async_block_till_done()
    assert services.installed == [], "must not run on a non-matching weekday"


async def test_scheduled_run_runs_on_matching_day(
    hass: HomeAssistant, services, freezer: FrozenDateTimeFactory
) -> None:
    """An entry pinned to the current weekday does run."""
    trigger = dt_util.now().replace(hour=3, minute=0, second=0, microsecond=0)
    freezer.move_to(trigger)
    today = WEEKDAYS[trigger.weekday()]

    entry = make_entry(**{CONF_FREQUENCY: "scheduled", CONF_DAY: today, CONF_TIME: "03:00:00"})
    await setup_integration(hass, entry)
    set_state(hass, ADDON, "on")

    async_fire_time_changed(hass, trigger)
    await hass.async_block_till_done()
    assert services.installed == [ADDON]


async def test_interval_run_fires(hass: HomeAssistant, services) -> None:
    """An interval entry runs when the interval elapses."""
    entry = make_entry(**{CONF_FREQUENCY: "hourly"})
    await setup_integration(hass, entry)
    set_state(hass, ADDON, "on")

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
    await hass.async_block_till_done()

    assert services.installed == [ADDON]
    assert store_for(hass, entry)[DATA_LAST_INSTALLED] == [ADDON]


async def test_interval_run_does_not_fire_early(hass: HomeAssistant, services) -> None:
    """An interval entry stays quiet before the interval elapses."""
    entry = make_entry(**{CONF_FREQUENCY: "every_6_hours"})
    await setup_integration(hass, entry)
    set_state(hass, ADDON, "on")

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
    await hass.async_block_till_done()
    assert services.installed == []

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=6))
    await hass.async_block_till_done()
    assert services.installed == [ADDON]


async def test_unload_cancels_scheduled_trigger(hass: HomeAssistant, services) -> None:
    """Unloading the entry removes its timer, so nothing runs afterwards."""
    entry = make_entry(**{CONF_FREQUENCY: "scheduled", CONF_DAY: "daily", CONF_TIME: "03:00:00"})
    await setup_integration(hass, entry)
    set_state(hass, ADDON, "on")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + datetime.timedelta(hours=1))
    await hass.async_block_till_done()
    assert services.installed == []
