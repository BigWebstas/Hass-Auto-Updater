"""Config flow for the Auto Updater integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DAY,
    CONF_FREQUENCY,
    CONF_REBOOT_WINDOW,
    CONF_TIME,
    DAY_DAILY,
    DAYS,
    DEFAULT_TIME,
    DOMAIN,
    FREQUENCIES,
    FREQUENCY_SCHEDULED,
)


def _frequency_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_FREQUENCY, default=defaults.get(CONF_FREQUENCY, FREQUENCY_SCHEDULED)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=FREQUENCIES,
                    translation_key="frequency",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            # suggested_value (not default) so the field can be cleared on reconfigure.
            vol.Optional(
                CONF_REBOOT_WINDOW, description={"suggested_value": defaults.get(CONF_REBOOT_WINDOW)}
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="schedule")),
        }
    )


def _schedule_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_DAY, default=defaults.get(CONF_DAY, DAY_DAILY)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=DAYS, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(CONF_TIME, default=defaults.get(CONF_TIME, DEFAULT_TIME)): selector.TimeSelector(),
        }
    )


class HassAutoUpdaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup and reconfiguration of the Auto Updater schedule."""

    VERSION = 1

    def __init__(self) -> None:
        # Frequency-step answers, carried into the day/time step.
        self._frequency_input: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_FREQUENCY] == FREQUENCY_SCHEDULED:
                self._frequency_input = user_input
                return await self.async_step_schedule()
            return self.async_create_entry(title="Auto Updater", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_frequency_schema())

    async def async_step_schedule(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Auto Updater", data={**self._frequency_input, **user_input}
            )
        return self.async_show_form(step_id="schedule", data_schema=_schedule_schema())

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            if user_input[CONF_FREQUENCY] == FREQUENCY_SCHEDULED:
                self._frequency_input = user_input
                return await self.async_step_reconfigure_schedule()
            return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(step_id="reconfigure", data_schema=_frequency_schema(entry.data))

    async def async_step_reconfigure_schedule(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry, data={**self._frequency_input, **user_input}
            )
        return self.async_show_form(step_id="reconfigure_schedule", data_schema=_schedule_schema(entry.data))
