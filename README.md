# Armoury Crate (unofficial Linux controls)

A community-built GTK4/libadwaita control center for supported ASUS laptops. It is an independent project and is not affiliated with or endorsed by ASUS. ASUS, ROG, TUF, and Armoury Crate are trademarks of their respective owners.

## Features

- Live CPU/GPU temperatures, fan speeds, RAM and storage usage.
- ASUS performance profiles and battery charge limit.
- Keyboard backlight controls and supported Aura effects.
- Integrated/hybrid GPU mode through `supergfxctl`.

Hardware support varies by laptop and firmware. Unsupported controls are not emulated: this app does not provide custom fan curves or per-key RGB where the firmware exposes no Linux interface.

## Requirements

- Fedora Linux with Python 3, GTK 4, libadwaita, and PyGObject.
- `asusctl` for ASUS profile, battery, and keyboard-lighting controls.
- `supergfxctl` for GPU mode switching (optional).
- An ASUS laptop with the corresponding kernel/firmware interfaces.

Install the runtime packages using Fedora's package manager, then run:

```sh
./install-armoury-fedora.sh install
```

The installer places the app in the current user's `~/.local` directories. To remove it:

```sh
./install-armoury-fedora.sh uninstall
```

## Artwork

The repository intentionally excludes images and artwork extracted from ASUS Windows packages. The application uses desktop symbolic-icon fallbacks when optional local artwork is absent. Do not redistribute ASUS assets without permission from the rights holder.

## Safety

This app can change supported hardware settings. Review the source before running it, and only use it on hardware you own or are authorized to manage. It does not bundle privileged services or perform automatic installation of system packages.
