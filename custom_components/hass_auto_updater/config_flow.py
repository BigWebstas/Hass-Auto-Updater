"""Config flow for the Auto Updater integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import CONF_DAY, CONF_TIME, DAY_DAILY, DAYS, DEFAULT_TIME, DOMAIN


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
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

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Auto Updater", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema())

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(entry.data))
