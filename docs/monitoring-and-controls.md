# Monitoring and hardware controls

This guide describes the live telemetry and controls exposed by the Linux app.
The app reads the interfaces provided by the kernel and installed ASUS tools; it
does not synthesize sensor values. A metric can be unavailable on systems whose
firmware or driver does not expose its sensor.

## Device page

The **Resource Monitor** tab plots the visible metrics and lists their latest
readings. Choose one of four levels:

| Level | Metrics shown |
| --- | --- |
| 1 · Essentials | CPU usage |
| 2 · Load & Thermals | CPU and GPU usage and temperature |
| 3 · Clocks & Memory | Level 2, CPU/GPU frequency, system memory usage, and GPU memory usage |
| 4 · Full Telemetry | Level 3, disk active time, disk read/write speed, and CPU/GPU fan speed |

The chart keeps up to ten minutes of samples and can display a 1-, 5-, or
10-minute window. Samples are collected once per second while the page is open.
**Stop** pauses chart history; current readings and the applications view continue
to refresh. Disk speed and active-time values need two samples before they can
be calculated.

The main data sources are:

- CPU usage: deltas from `/proc/stat`; CPU frequency from the available CPU
  frequency interface; temperature from `acpitz`, `k10temp`, or `coretemp` hwmon.
- GPU: `nvidia-smi` when available, otherwise Linux DRM sysfs and hwmon values.
  NVIDIA command readings are cached briefly to limit overhead.
- Memory: `/proc/meminfo`; disk activity and throughput: `/proc/diskstats`.
- Fan speed: ASUS hwmon fan inputs where exposed by the firmware.

The **Running Applications** tab groups process rows by a normalized display
name where a mapping is known. CPU percentage and resident memory are read from
`ps`; multiple matching processes are combined. The list refreshes about every
four seconds and includes the busiest processes by CPU and memory, not every
process on the system.

The **Device Details** tab shows detected processor topology, CPU frequency and
temperature, system memory and swap, available discrete and integrated GPU
telemetry, and detected physical drives. SSD/HDD health fields come from
`smartctl` when the device and permissions allow access. The first read is
cached in the user's XDG cache directory and reused across application
restarts. It is read again only when **Refresh SMART** is selected. Fields that
the drive or driver does not expose are omitted; an unavailable field does not
indicate a drive failure.

## Dashboard

The dashboard summarizes system identity and the available CPU, graphics,
memory, storage, battery, fan, ASUS profile, and GPU-mode data. Battery time is
an estimate from charge/energy and current/power readings when those values are
available. It is omitted when the hardware does not provide enough information.

## Hardware controls

- **Scenario Profiles:** Quiet, Balanced, and Performance use `asusctl profile
  set` first, with desktop power-profile and ASUS D-Bus fallbacks when needed.
- **Keyboard Lighting:** supported Aura effects are applied through `asusctl`.
  Color options depend on the selected effect. The keyboard brightness control
  uses the firmware's four supported levels: Off, Low, Medium, and High.
- **Graphics mode:** Integrated and Hybrid are provided by `supergfxctl` when
  supported. Some systems require logging out or restarting for a graphics-mode
  change to take effect.
- **Battery charge limit:** the app uses the ASUS service or kernel charge-limit
  interface when available.

The app does not provide custom fan curves or per-key lighting when those
controls are absent from the machine's Linux interfaces.
