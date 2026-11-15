# Armoury Crate for Linux (unofficial)

A community-built GTK4/libadwaita control center for supported ASUS laptops. It is an independent project and is not affiliated with or endorsed by ASUS. ASUS, ROG, TUF, and Armoury Crate are trademarks of their respective owners.

## Features

- Dashboard with device, processor, graphics, operating-system, CPU, memory, storage, battery, fan, and GPU-mode details.
- Device page with separate **Resource Monitor** and **Running Applications** views. The monitor plots live CPU/GPU, memory, disk, and fan telemetry, with four metric levels and 1-, 5-, or 10-minute history views. Sensor coverage depends on the hardware and available Linux drivers.
- Running application usage grouped by process name, with CPU and resident-memory readings.
- ASUS Quiet, Balanced, and Performance profiles, plus supported battery charge-limit controls.
- Keyboard backlight controls and supported Aura effects, with a multi-row effect picker, color presets, and the native color picker.
- Integrated/hybrid GPU mode through `supergfxctl`.

Telemetry is read from Linux interfaces such as `/proc`, `/sys`, hwmon, and available vendor utilities. Missing or unsupported sensors are shown as unavailable; support varies by laptop, firmware, GPU, and installed drivers.

See [the monitoring and hardware support guide](docs/monitoring-and-controls.md) for metric levels, data sources, and known limitations.

## Source layout

- `src/app.py` and `src/window.py` provide startup and the shared application shell.
- `src/pages/` contains the dashboard, device, cooling, battery, lighting, and GPU pages.
- `src/components/` contains reusable GTK widgets; `src/hardware/` contains Linux telemetry and ASUS control integrations.
- `src/config.py` and `src/styles.py` hold app settings and shared GTK styling.
- `assets/` contains optional artwork and UI icons.
- `packaging/` contains RPM and DEB build definitions.
- `install.sh` checks ASUS hardware compatibility and runtime dependencies, offers to install missing packages from configured distribution repositories, then installs the app for the current user. `uninstall.sh` removes the app files without removing system dependencies.

Hardware support varies by laptop and firmware. Unsupported controls are not emulated: this app does not provide custom fan curves or per-key RGB where the firmware exposes no Linux interface.

## Requirements

- A Linux desktop with Python 3, GTK 4, libadwaita, and PyGObject.
- `asusctl` for ASUS profile, battery, and keyboard-lighting controls.
- `supergfxctl` for GPU mode switching.
- `ps` (from `procps`) for the Running Applications view.
- `nvidia-smi` is optional and used for NVIDIA telemetry when available; AMD/Linux DRM sysfs sensors are used where exposed.
- An ASUS laptop with the corresponding kernel/firmware interfaces.

Run the installer from the downloaded or cloned project directory:

```sh
./install.sh
```

The installer checks for `asusctl`, `supergfxctl`, GTK 4, libadwaita, PyGObject, `pciutils`, and `procps`. It supports APT, DNF/YUM, Pacman, Zypper, APK, XBPS, Emerge, and Eopkg based distributions. It asks before installing missing packages and uses `sudo` for system package operations. On Fedora it offers the Terra repository; on Arch it offers the signed OGC repository. Other distributions need the ASUS utility packages available in their configured repositories. NixOS needs its declarative service configuration, so the installer reports that requirement instead of editing `/etc/nixos` automatically. ASUS Linux's supported distro list and package availability change over time; check its [current distro documentation](https://github.com/OpenGamingCollective/asusctl/blob/main/docs/getting-started/supported-distributions.md) if a package is missing. Hardware support also depends on the laptop model, kernel, and firmware.

The app is installed in the current user's `~/.local` directories. To remove it:

```sh
./uninstall.sh
```

## Packages

RPM and DEB packages are built for tagged releases and attached to the GitHub release. Both packages require `asusctl` and `supergfxctl`, in addition to the GTK/Python runtime dependencies. Install the matching service packages from repositories supported by your distribution before installing Armoury Crate.

To build packages locally, install `rpmbuild` and `dpkg-deb`, then run:

```sh
./packaging/build-packages.sh
```

Artifacts are written to `dist/`.

## Artwork

The repository intentionally excludes images and artwork extracted from ASUS Windows packages. The application uses desktop symbolic-icon fallbacks when optional local artwork is absent. Do not redistribute ASUS assets without permission from the rights holder.

## Safety

This app can change supported hardware settings. Review the source before running it, and only use it on hardware you own or are authorized to manage. It does not bundle privileged services or perform automatic installation of system packages.
