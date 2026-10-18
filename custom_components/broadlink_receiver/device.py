"""Create receiver connections using the library supplied by Core."""

from collections.abc import Mapping
from inspect import iscoroutinefunction
from typing import Any

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_DEV_TYPE

# Core 2026.10.2 switched from python-broadlink (imported as `broadlink`) to
# broadlink-async (imported as `broadlink_async`); both share the same API.
try:
    import broadlink_async as blk
    from broadlink_async.exceptions import (
        BroadlinkException,
        ReadError,
        StorageError,
    )
    from broadlink_async.remote import data_to_pulses, rmmini
except ImportError:
    import broadlink as blk
    from broadlink.exceptions import BroadlinkException, ReadError, StorageError
    from broadlink.remote import data_to_pulses, rmmini

__all__ = [
    "BroadlinkException",
    "ReadError",
    "StorageError",
    "check_library",
    "create_device",
    "data_to_pulses",
    "rmmini",
]


def check_library() -> None:
    """Reject the old synchronous package before it can open a socket."""
    if not iscoroutinefunction(blk.Device.auth) or not iscoroutinefunction(
        getattr(blk.Device, "aclose", None)
    ):
        raise ConfigEntryError(
            "Broadlink IR Receiver requires Home Assistant 2026.10 or later "
            "and Core's async Broadlink library. Remove the conflicting "
            "broadlink distribution and restore Core's requirements, then "
            "restart Home Assistant."
        )


def create_device(data: Mapping[str, Any], name: str) -> rmmini:
    """Create a separate RM connection without using Core's device instance."""
    check_library()
    mac = data[CONF_MAC]
    if isinstance(mac, str):
        mac = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    else:
        mac = bytes(mac)

    device = blk.gendevice(
        data[CONF_DEV_TYPE],
        (data[CONF_HOST], data.get(CONF_PORT, 80)),
        mac,
        name=name,
    )
    if not isinstance(device, rmmini):
        raise ConfigEntryError("This Broadlink device does not support IR learning.")
    device.timeout = 10
    return device
