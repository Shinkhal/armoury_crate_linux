# Changelog

Notable user-facing changes are listed here. Older release details are
available in the [GitHub releases](https://github.com/Shinkhal/armoury_crate_linux/releases).

## 0.4.1 — 2026-11-25

- Make GUI regression tests skip cleanly when GTK/PyGObject is not installed in package-build environments.

## 0.4.0 — 2026-11-24

- Add a System Configuration workspace with embedded GPU Performance and Lighting views.
- Improve GPU mode backend selection, asynchronous switching, restart prompting, and post-reboot state reporting.
- Redesign Device Details and remove the redundant Operating Mode page.
- Improve capability detection and touchpad control through desktop settings.

## 0.3.0 — 2026-11-16

- Add a Device Details view for processor, memory, graphics, and physical-drive
  information.
- Read SSD/HDD health through `smartmontools`, persist results across app
  restarts, and refresh them only when requested by the user.
- Improve CPU frequency/topology and hybrid GPU telemetry.
- Add installer and package dependencies for Pycairo and `smartmontools`.
- Improve CI import smoke checks and battery aggregation.
