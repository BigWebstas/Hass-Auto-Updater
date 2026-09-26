"""Constants for the Auto Updater integration."""

from homeassistant.const import Platform

DOMAIN = "hass_auto_updater"

CONF_FREQUENCY = "frequency"
CONF_DAY = "day"
CONF_TIME = "time"

# Run at a specific day/time (uses CONF_DAY + CONF_TIME below).
FREQUENCY_SCHEDULED = "scheduled"

# Run repeatedly on a fixed interval, independent of CONF_DAY/CONF_TIME.
FREQUENCY_INTERVALS = {
    "hourly": 1,
    "every_6_hours": 6,
    "every_12_hours": 12,
}

FREQUENCIES = [FREQUENCY_SCHEDULED, *FREQUENCY_INTERVALS]

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
