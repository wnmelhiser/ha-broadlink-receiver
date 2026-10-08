"""Config flow for the Broadlink IR Receiver integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from broadlink.exceptions import BroadlinkException
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_DEV_TYPE, DOMAIN
from .device import check_library, create_device

_LOGGER = logging.getLogger(__name__)

CONF_BROADLINK_ENTRY = "broadlink_entry"


class BroadlinkReceiverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Broadlink IR Receiver."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user pick which of their existing Broadlink devices to add RX to."""
        try:
            check_library()
        except ConfigEntryError as err:
            _LOGGER.error("%s", err)
            return self.async_abort(reason="unsupported_library")

        broadlink_entries = self.hass.config_entries.async_entries("broadlink")

        if not broadlink_entries:
            return self.async_abort(reason="no_broadlink_devices")

        # Only offer devices that don't already have a receiver entry.
        existing = {
            entry.data.get("broadlink_entry_id")
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        }
        available = [e for e in broadlink_entries if e.entry_id not in existing]

        if not available:
            return self.async_abort(reason="all_devices_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            source_entry = next(
                (
                    e
                    for e in available
                    if e.entry_id == user_input[CONF_BROADLINK_ENTRY]
                ),
                None,
            )
            if source_entry is None:
                errors["base"] = "unknown_device"
            else:
                host = source_entry.data.get(CONF_HOST)
                mac = source_entry.data.get(CONF_MAC)
                dev_type = source_entry.data.get(CONF_TYPE)
                port = source_entry.data.get(CONF_PORT, 80)

                if host is None or mac is None or dev_type is None:
                    errors["base"] = "missing_device_info"
                else:
                    mac_str = (
                        mac.hex(":")
                        if isinstance(mac, (bytes, bytearray))
                        else str(mac)
                    )
                    await self.async_set_unique_id(mac_str)
                    self._abort_if_unique_id_configured()

                    data = {
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_MAC: mac,
                        CONF_DEV_TYPE: dev_type,
                        "broadlink_entry_id": source_entry.entry_id,
                    }
                    try:
                        device = create_device(data, source_entry.title)
                    except (ConfigEntryError, ValueError) as err:
                        _LOGGER.error("Cannot receive IR from %s: %s", host, err)
                        errors["base"] = "unsupported_device"
                    else:
                        try:
                            try:
                                await device.auth()
                            except (BroadlinkException, OSError) as err:
                                _LOGGER.debug("Could not connect to %s: %s", host, err)
                                errors["base"] = "cannot_connect"
                            else:
                                return self.async_create_entry(
                                    title=f"{source_entry.title} (IR Receiver)",
                                    data=data,
                                )
                        finally:
                            await device.aclose()

        options = [SelectOptionDict(value=e.entry_id, label=e.title) for e in available]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROADLINK_ENTRY): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                }
            ),
            errors=errors,
        )
