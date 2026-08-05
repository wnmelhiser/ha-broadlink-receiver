# Changelog

All notable changes to this project are documented here.

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
