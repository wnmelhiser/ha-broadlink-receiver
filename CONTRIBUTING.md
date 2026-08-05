# Contributing

Issues and PRs are welcome.

## Development

This is a standard HACS-style custom integration:

```
custom_components/broadlink_receiver/
```

To test changes, copy that folder into a test HA instance's
`config/custom_components/`, restart HA, and enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.broadlink_receiver: debug
```

or at runtime via **Developer Tools → Actions → `logger.set_level`**:

```yaml
custom_components.broadlink_receiver.infrared: debug
```

## Before submitting a PR

- Run `python -m py_compile custom_components/broadlink_receiver/*.py`
- If you have access to `home-assistant/core` locally, running `hassfest`
  against this repo catches manifest/schema issues before CI does
- Update `CHANGELOG.md`

## Reporting a device that doesn't work

Please include your Broadlink model, HA version, and a debug log capturing
one full attempted signal capture (see the README's Troubleshooting
section for what a healthy log looks like) — the
[bug report template](.github/ISSUE_TEMPLATE/bug_report.md) has the
checklist.
