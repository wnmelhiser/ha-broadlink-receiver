"""The Broadlink IR Receiver integration.

This integration exists to fill a specific gap: as of HA 2026.6, the
`infrared` platform ships `InfraredReceiverEntity` for RX, and ESPHome /
SMLIGHT already implement it -- but the core `broadlink` integration only
implements the emitter (TX) side. This integration opens a second,
receive-only connection to a Broadlink RM device you've already configured
in core Home Assistant, and exposes its learning/capture capability as a
native `InfraredReceiverEntity` so any consumer of the infrared platform
(including tools like HAIR) can use it as a receiver.

It does not replace or modify your existing `broadlink` config entry or its
`remote.send_command` / `remote.learn_command` services -- those keep
working exactly as before.
"""
from __future__ import annotations

import logging

import broadlink as blk
from broadlink.exceptions import BroadlinkException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DEV_TYPE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.INFRARED] if hasattr(Platform, "INFRARED") else ["infrared"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Broadlink IR Receiver config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 80)
    mac = entry.data[CONF_MAC]
    dev_type = entry.data[CONF_DEV_TYPE]

    device = blk.gendevice(dev_type, (host, port), mac)
    device.timeout = 10

    try:
        await hass.async_add_executor_job(device.auth)
    except (BroadlinkException, OSError) as err:
        raise ConfigEntryNotReady(
            f"Could not authenticate with Broadlink device at {host}: {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Broadlink IR Receiver config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
