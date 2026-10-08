# Broadlink IR Receiver

[![Validate](https://github.com/wnmelhiser/ha-broadlink-receiver/actions/workflows/validate.yml/badge.svg)](https://github.com/wnmelhiser/ha-broadlink-receiver/actions/workflows/validate.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/wnmelhiser/ha-broadlink-receiver)](https://github.com/wnmelhiser/ha-broadlink-receiver/releases)

Custom Home Assistant integration that exposes a Broadlink RM device's IR
learning capability as a native **`InfraredReceiverEntity`** (requires HA
2026.10+).

## Why this exists

HA's native `infrared` platform shipped transmit (TX) support in 2026.4 and
receive (RX) support via `InfraredReceiverEntity` in 2026.6. The core
`broadlink` integration has only implemented the **emitter** side — your
Broadlink device can send learned codes through the new platform, but it
can't act as a receiver for it. That means tools built on the RX side of the
platform (like [HAIR](https://github.com/DAB-LABS/HAIR)'s Sniffer) can't use
a Broadlink device to capture signals, even though the hardware is fully
capable of it — the RM3 mini's IR learning has always worked via the older
`remote.learn_command` service, there's just no bridge from that into the
new receiver entity API yet.

This integration is that bridge.

## How it works

Broadlink's protocol has no push/streaming mode for captured IR signals.
Capturing one is a two-step, asynchronous process — `await enter_learning()` arms the
device, then `check_data()` is polled until a signal shows up. This
integration awaits both operations in a cancellable background task, re-arming learning mode
every ~15 seconds so it behaves like a continuous sniffer instead of a
single learn-one-code operation, and forwards every captured signal to HA's
native receiver entity API as soon as it lands.

It opens its **own** authenticated connection to the device, separate from
the core `broadlink` integration's connection. It doesn't touch your
existing config entry, `remote.send_command`, or `remote.learn_command` —
those keep working exactly as before.

The manifest depends on Core's `broadlink` integration and deliberately has
no library requirement of its own. Home Assistant installs the version
pinned by Core (`python-broadlink==1.0.6` in HA 2026.10, imported as
`broadlink`). This integration never installs or pins the conflicting PyPI
distribution `broadlink`. The polling task is cancelled and its UDP endpoint
closed when the entity is removed, the integration is unloaded, or HA stops.

## Requirements

- Home Assistant **2026.10** or later (for Core's async Broadlink library;
  the native `InfraredReceiverEntity` API itself was added in 2026.6)
- The core **Broadlink** integration already set up with your RM device
- A Broadlink device with IR receive hardware (RM mini/RM mini 3/RM pro/RM4
  series — i.e. anything that already supports `remote.learn_command`
  today)

## Installation

### HACS (custom repository)

[![Add Repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=wnmelhiser&repository=ha-broadlink-receiver&category=integration)

Or manually:

1. HACS → the three-dot menu (top right) → **Custom repositories**
2. Add `https://github.com/wnmelhiser/ha-broadlink-receiver`, category **Integration**
3. Install, then restart Home Assistant

### Manual

1. Copy `custom_components/broadlink_receiver` into your HA
   `config/custom_components/` directory
2. Restart Home Assistant

## Setup

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=broadlink_receiver)

Or manually:

1. **Settings → Devices & Services → Add Integration**
2. Search for **Broadlink IR Receiver**
3. Pick which of your already-configured Broadlink devices to add a
   receiver entity for
4. Done — a new `infrared` receiver entity appears for that device, and any
   consumer of the native infrared platform (HAIR's Sniffer, a
   `universal_remote` helper, automations triggered on IR signals, etc.)
   can subscribe to it

## Troubleshooting

Enable debug logging (Developer Tools → Actions → `logger.set_level`, or in
`configuration.yaml`):

```yaml
logger:
  default: info
  logs:
    custom_components.broadlink_receiver.infrared: debug
```

A healthy receiver logs a `(re)armed learning mode` line roughly every 15
seconds, and a `captured signal with N timings` line each time you press a
remote button in range. If you see the arm messages but never a capture
message when pressing a button, the device likely isn't receiving the
`enter_learning()` call (check host/IP and that nothing else has the device
in a conflicting state) — if you see neither, the background task isn't
running; check the Home Assistant log around integration startup for a
traceback.

If the entity's state stays `unknown` even though capture-log lines are
appearing, check the Home Assistant log for a `RuntimeError` mentioning
`async_write_ha_state` and a thread other than the event loop — this was a
real bug in 0.1.0, fixed in 0.1.1 by using `hass.loop.call_soon_threadsafe`
instead of `hass.add_job`. If you see it on a version at or after 0.1.1,
please open an issue.

### Upgrading from the conflicting library

Earlier versions installed `broadlink==0.19.0`, which writes to the same
`broadlink` module directory as `python-broadlink`. Updating this integration
removes that requirement but does not automatically uninstall the old
distribution or repair files it overwrote. Restart Home Assistant after
updating. If the log still reports an unsupported library or missing
Broadlink imports, repair the Python environment used by HA: remove the
old `broadlink` distribution and reinstall **the `python-broadlink` version
pinned by your installed Core release**, then restart HA again. Removing
only the old package can also remove shared module files, so reinstalling
Core's package afterward is essential.

For HA OS or Container, use your installation's supported update/rebuild
procedure to restore a clean managed environment rather than installing
Python packages in an unrelated shell environment. Do not add a replacement
library pin to this custom integration's manifest.

## Known limitations

- **Don't run `remote.learn_command` on the core Broadlink entity while
  this receiver is active.** Both use the same physical device's learning
  mode; running them at the same time means they'll race for the same
  capture window. Pause one before using the other.
- **Polling, not push.** There's a sub-second-to-~1-second delay between a
  button press and the signal reaching HA, because this is fundamentally a
  poll loop, not a hardware interrupt. In practice this is fine for
  learning/sniffing but don't expect zero-latency automation triggers.
- **One receiver connection per device.** Adding the integration twice for
  the same physical Broadlink device isn't supported (the config flow won't
  offer a device that's already configured).
- Uses Core's async `python-broadlink` API (`rmmini` and its subclasses,
  including `rm4mini`/`rm4pro`). Devices without IR learning support cannot
  be added. Very old firmware revisions with nonstandard `check_data`
  behavior haven't been tested — please open an issue with your device's
  reported type if something doesn't work.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports, especially from
Broadlink models other than the RM mini 3, are particularly useful.

## Contributing upstream

If this proves solid across more devices, the natural next step is
contributing RX support directly to core's `broadlink` integration (the way
TX support was added in May 2026) rather than maintaining it as a separate
custom component forever. This repo is deliberately structured close to
core conventions to make that migration easy later.

## License

[MIT](LICENSE)
