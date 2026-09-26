"""Constants for the Auto Updater integration."""

from homeassistant.const import Platform

DOMAIN = "hass_auto_updater"

CONF_DAY = "day"
CONF_TIME = "time"

DAY_DAILY = "daily"
DAYS = [
    DAY_DAILY,
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

DEFAULT_TIME = "03:00:00"

# Key inside hass.data[DOMAIN][entry_id] holding whether scheduled runs are enabled.
DATA_ENABLED = "enabled"

PLATFORMS = [Platform.SWITCH]

# Installed last: these can trigger their own HA/Supervisor restart mid-run,
# so everything else should finish installing first.
INSTALL_LAST_PREFIXES = (
    "update.home_assistant_core",
    "update.home_assistant_supervisor",
    "update.home_assistant_operating_system",
)
