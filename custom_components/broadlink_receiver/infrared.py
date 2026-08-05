"""Infrared receiver platform for Broadlink RM devices.

Broadlink's protocol has no push/streaming mode for captured IR signals.
Capturing a signal is a two-step, blocking process:

    device.enter_learning()      # arm the device
    device.check_data()          # raises ReadError until a signal lands,
                                  # then returns the raw packet bytes

This platform runs that loop on a dedicated background thread (the
`broadlink` library is fully synchronous/blocking socket I/O, so it cannot
run on the event loop) and re-arms learning mode periodically so it behaves
like a continuous sniffer rather than a single learn-one-code operation.
Whenever a signal is captured, it's converted to microsecond pulse timings
and handed to HA's native InfraredReceiverEntity via
`hass.loop.call_soon_threadsafe`, which unconditionally runs the call on
the event loop -- unlike `hass.add_job`, which for a plain (non-`@callback`)
method may instead dispatch it to an executor thread, still off the event
loop, causing `async_write_ha_state()` inside `_handle_received_signal` to
fail its thread-safety check silently.
"""
from __future__ import annotations

import logging
import threading
import time

from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from broadlink.remote import data_to_pulses

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

    def __init__(self, entry: ConfigEntry, device) -> None:
        """Initialize the receiver entity."""
        self._device = device
        self._entry = entry
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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
        """Start the capture thread once the entity is registered."""
        await super().async_added_to_hass()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name=f"broadlink_receiver-{self._attr_unique_id}",
            daemon=True,
        )
        self._thread.start()

    async def async_will_remove_from_hass(self) -> None:
        """Stop the capture thread on removal/unload."""
        self._stop_event.set()
        if self._thread is not None:
            await self.hass.async_add_executor_job(self._thread.join, 5)
        await super().async_will_remove_from_hass()

    def _poll_loop(self) -> None:
        """Continuously arm learning mode and poll for captured signals.

        Runs entirely on the background thread. Never touches `self.hass`
        directly except through `hass.loop.call_soon_threadsafe`, the
        thread-safe entry point back into the event loop.
        """
        last_arm_time = 0.0

        while not self._stop_event.is_set():
            now = time.monotonic()

            if now - last_arm_time >= LEARNING_REARM_INTERVAL:
                try:
                    self._device.enter_learning()
                    last_arm_time = now
                    _LOGGER.debug(
                        "%s: (re)armed learning mode", self._attr_unique_id
                    )
                except (BroadlinkException, OSError) as err:
                    _LOGGER.debug(
                        "Failed to (re)arm learning mode on %s: %s",
                        self._attr_unique_id,
                        err,
                    )
                    self._stop_event.wait(LEARNING_REARM_INTERVAL)
                    continue

            try:
                payload = self._device.check_data()
            except (ReadError, StorageError):
                # No signal captured yet -- this is the normal, expected
                # result of almost every poll.
                self._stop_event.wait(POLL_INTERVAL)
                continue
            except (BroadlinkException, OSError) as err:
                _LOGGER.debug(
                    "Error polling %s for IR data: %s", self._attr_unique_id, err
                )
                self._stop_event.wait(POLL_INTERVAL)
                continue

            try:
                timings = data_to_pulses(payload)
            except (ValueError, IndexError) as err:
                _LOGGER.debug("Discarding malformed IR packet: %s", err)
                continue

            if timings:
                signal = InfraredReceivedSignal(timings=timings, modulation=None)
                self.hass.loop.call_soon_threadsafe(
                    self._handle_received_signal, signal
                )
                _LOGGER.debug(
                    "%s: captured signal with %d timings",
                    self._attr_unique_id,
                    len(timings),
                )

            # A signal just came in -- re-arm immediately on the next loop
            # iteration so back-to-back button presses aren't missed.
            last_arm_time = 0.0
