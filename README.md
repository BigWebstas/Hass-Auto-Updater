# Hass Auto Updater

A custom Home Assistant integration that installs pending updates on a schedule and restarts Home Assistant if anything was installed. A switch lets you pause and resume the schedule.

## What it does

- On the schedule you configure, it checks every `update.*` entity (HA Core, Supervisor, HAOS, add-ons, HACS integrations — whatever's present).
- Installs any update that's available (`update.install`), installing HA Core/Supervisor/OS last so add-ons and other updates get a chance to finish first.
- If anything was installed, calls `homeassistant.restart`.
- Optional **reboot window**: pick a [Schedule helper](https://www.home-assistant.io/integrations/schedule/) (`schedule.*`). Updates install and HA restarts only while that schedule is on. A run that falls outside it waits and runs as soon as the schedule turns on.
- Adds a `switch.auto_updater_enabled` entity — turn it off to pause scheduled runs; turn it back on to resume. State survives restarts.

## Install

1. Copy `custom_components/hass_auto_updater` into your Home Assistant config's `custom_components` folder.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **Auto Updater**.
4. Choose a frequency:
   - **Specific day & time** — pick a day (or "daily") and a time.
   - **Every hour**, **every 6 hours**, or **every 12 hours** — runs on that fixed interval instead, no day/time needed.
5. Optionally choose a reboot window schedule. Create one first under Settings → Devices & Services → Helpers → **Schedule**.

To change the schedule later, open the integration's entry and choose **Reconfigure** — no need to remove and re-add it.

## Known limitations

- If installing the HA Core or Supervisor update triggers its own restart mid-run, any updates still queued after it won't get installed in that pass — they'll be picked up on the next scheduled run.
- Interval schedules (hourly / every 6h / every 12h) count from whenever the integration was last set up or Home Assistant restarted — they're not aligned to clock boundaries like midnight or 06:00.
- A run deferred by the reboot window is remembered in memory only. If Home Assistant restarts before the window opens, that run is dropped and the next scheduled run picks the updates up.
