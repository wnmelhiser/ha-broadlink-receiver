# Changelog

All notable changes to this project are documented here.

## [0.2.0] - 2026-10-09

### Fixed
- Use the Broadlink library pinned by Home Assistant Core through the
  existing integration dependency, instead of installing the conflicting
  `broadlink==0.19.0` distribution.
- Await authentication, learning and polling with Core's async API.
  Cancel capture tasks and close connections on removal, shutdown, failed
  setup and after config-flow probes.
- Normalize Core's stored MAC addresses before creating separate receiver
  connections, and reject devices without IR learning support.

### Changed
- Require Home Assistant 2026.10 or later, the first release using
  `python-broadlink`'s asynchronous API.

## [0.1.2] - 2026-08-05

### Fixed
- The brand icon never showed up in HACS or the HA integrations page because
  the `v0.1.1` release was cut before `custom_components/broadlink_receiver/brand/`
  was added to the repo — anyone installing via HACS got a tree with no icon
  assets in it at all, regardless of the fix landing on `main`. This release
  is the first to actually include `brand/icon.png` and `brand/logo.png`.

## [0.1.1] - 2026-08-04

### Fixed
- Signals captured on the background polling thread were never reaching the
  entity state. `hass.add_job()` does not guarantee a plain (non-`@callback`)
  method runs on the event loop — it can dispatch to an executor thread
  instead, which is still not the event loop, so `_handle_received_signal`'s
  internal `async_write_ha_state()` call failed HA's thread-safety check and
  the state silently never updated. Switched to
  `hass.loop.call_soon_threadsafe()`, which unconditionally runs the
  callback on the event loop.
- Added a debug log line on successful capture and on each learning-mode
  (re)arm, so a stuck receiver can be diagnosed from logs alone going
  forward.

## [0.1.0] - 2026-08-04

### Added
- Initial release. Config flow to attach an IR receiver to an existing core
  `broadlink` device entry. Background-thread `enter_learning()` /
  `check_data()` poll loop exposed as a native `InfraredReceiverEntity`
  (requires HA 2026.6+).
