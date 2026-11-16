# Changelog

Notable user-facing changes are listed here. Older release details are
available in the [GitHub releases](https://github.com/Shinkhal/armoury_crate_linux/releases).

## 0.3.0 — 2026-11-16

- Add a Device Details view for processor, memory, graphics, and physical-drive
  information.
- Read SSD/HDD health through `smartmontools`, persist results across app
  restarts, and refresh them only when requested by the user.
- Improve CPU frequency/topology and hybrid GPU telemetry.
- Add installer and package dependencies for Pycairo and `smartmontools`.
- Improve CI import smoke checks and battery aggregation.
