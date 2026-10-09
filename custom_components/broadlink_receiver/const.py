"""Constants for the Broadlink IR Receiver integration."""

from __future__ import annotations

DOMAIN = "broadlink_receiver"

CONF_DEV_TYPE = "dev_type"
CONF_SOURCE_ENTRY_ID = "source_entry_id"

# How long (seconds) a single enter_learning() window is trusted before we
# proactively re-arm it. Broadlink devices don't document an official
# learning-mode timeout, so this mirrors the conservative interval used by
# other local Broadlink tooling (broadlink-mqtt, HA core's own learn step).
LEARNING_REARM_INTERVAL = 15

# How long to sleep between check_data() polls. Broadlink's protocol has no
# push/streaming mode for captured signals -- this is a poll, not a
# subscription, so this interval is the effective "reaction time" of the
# receiver.
POLL_INTERVAL = 1.0

MANUFACTURER = "Broadlink"
