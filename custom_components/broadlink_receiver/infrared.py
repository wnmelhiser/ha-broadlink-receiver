"""Infrared receiver platform for Broadlink RM devices.

Core's asynchronous Broadlink library arms learning mode and polls for
captured packets without blocking the event loop. A cancellable task re-arms
periodically and delivers decoded signals directly on the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from broadlink.remote import data_to_pulses, rmmini
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

try:
    from homeassistant.components.infrared import (
        InfraredReceivedSignal,
        InfraredReceiverEntity,
    )
except ImportError as err:  # pragma: no cover - guards against HA < 2026.6
    raise ImportError(
        "The native infrared platform (InfraredReceiverEntity) requires "
        "Home Assistant 2026.6 or later."
    ) from err

from .const import DOMAIN, LEARNING_REARM_INTERVAL, MANUFACTURER, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink IR receiver entity for this config entry."""
    device = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BroadlinkIRReceiver(entry, device)])


class BroadlinkIRReceiver(InfraredReceiverEntity):
    """An InfraredReceiverEntity backed by a Broadlink RM device's learning mode."""

    _attr_has_entity_name = True
    _attr_name = "IR Receiver"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, device: rmmini) -> None:
        """Initialize the receiver entity."""
        self._device = device
        self._entry = entry
        self._poll_task: asyncio.Task[None] | None = None

        mac = getattr(device, "mac", None)
        mac_str = mac.hex(":") if isinstance(mac, (bytes, bytearray)) else str(mac)

        self._attr_unique_id = f"{entry.entry_id}_ir_receiver"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=getattr(device, "name", None) or entry.title,
            manufacturer=MANUFACTURER,
            model=getattr(device, "model", None) or getattr(device, "type", None),
            connections={("mac", mac_str)} if mac_str else set(),
        )

    async def async_added_to_hass(self) -> None:
        """Start capture once the entity is registered."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_stop)
        )
        self._poll_task = self._entry.async_create_background_task(
            self.hass,
            self._async_poll_loop(),
            f"broadlink_receiver-{self._attr_unique_id}",
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel in-flight capture and close the endpoint on removal."""
        try:
            await self._async_stop()
        finally:
            await super().async_will_remove_from_hass()

    async def _async_stop(self, event: Event | None = None) -> None:
        """Stop capture on entity removal or Home Assistant shutdown."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
        await self._device.aclose()

    async def _async_poll_loop(self) -> None:
        """Continuously arm learning mode and poll for captured signals."""
        last_arm_time: float | None = None
        loop = asyncio.get_running_loop()

        try:
            while True:
                now = loop.time()

                if (
                    last_arm_time is None
                    or now - last_arm_time >= LEARNING_REARM_INTERVAL
                ):
                    try:
                        await self._device.enter_learning()
                    except (BroadlinkException, OSError) as err:
                        _LOGGER.debug(
                            "Failed to (re)arm learning mode on %s: %s",
                            self._attr_unique_id,
                            err,
                        )
                        await asyncio.sleep(LEARNING_REARM_INTERVAL)
                        continue
                    last_arm_time = loop.time()
                    _LOGGER.debug("%s: (re)armed learning mode", self._attr_unique_id)

                try:
                    payload = await self._device.check_data()
                except (ReadError, StorageError):
                    # No signal yet is the normal result of most polls.
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                except (BroadlinkException, OSError) as err:
                    _LOGGER.debug(
                        "Error polling %s for IR data: %s", self._attr_unique_id, err
                    )
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                # Even a malformed capture consumes the learning window.
                last_arm_time = None
                try:
                    timings = data_to_pulses(payload)
                except (ValueError, IndexError) as err:
                    _LOGGER.debug("Discarding malformed IR packet: %s", err)
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                if timings:
                    signal = InfraredReceivedSignal(timings=timings, modulation=None)
                    self._handle_received_signal(signal)
                    _LOGGER.debug(
                        "%s: captured signal with %d timings",
                        self._attr_unique_id,
                        len(timings),
                    )
                else:
                    await asyncio.sleep(POLL_INTERVAL)
        finally:
            await self._device.aclose()
