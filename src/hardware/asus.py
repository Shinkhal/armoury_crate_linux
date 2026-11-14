"""ASUS firmware controls exposed through asusd and Linux kernel interfaces."""
import glob
import os
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib

from config import ASUSD_NAME, ASUSD_PATH, BATTERY_PATHS, CHARGE_LIMITS, PLATFORM_IFACE, PROFILE_VALUES

_system_bus = None


def text(path, default="—"):
    try:
        with open(path, encoding="utf-8") as stream:
            return stream.read().strip() or default
    except OSError:
        return default


def int_or_none(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def command(args, timeout=12):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def power_adapter_online():
    paths = glob.glob("/sys/class/power_supply/AC*/online")
    paths.extend(glob.glob("/sys/class/power_supply/ADP*/online"))
    readings = [int_or_none(text(path, "")) for path in paths]
    readings = [reading for reading in readings if reading in (0, 1)]
    return any(readings) if readings else None


def system_bus():
    global _system_bus
    if _system_bus is None:
        try:
            _system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error:
            return None
    return _system_bus


def get_prop(name):
    bus = system_bus()
    if bus is None:
        return None
    try:
        result = bus.call_sync(
            ASUSD_NAME, ASUSD_PATH, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (PLATFORM_IFACE, name)),
            GLib.VariantType.new("(v)"), Gio.DBusCallFlags.NONE, 4000, None,
        )
        return result.unpack()[0]
    except GLib.Error:
        return None


def set_prop(name, variant):
    bus = system_bus()
    if bus is None:
        return False
    try:
        bus.call_sync(
            ASUSD_NAME, ASUSD_PATH, "org.freedesktop.DBus.Properties", "Set",
            GLib.Variant("(ssv)", (PLATFORM_IFACE, name, variant)), None,
            Gio.DBusCallFlags.NONE, 5000, None,
        )
        return True
    except GLib.Error:
        return False


def read_profile():
    value = int_or_none(get_prop("PlatformProfile"))
    if value is not None:
        return PROFILE_VALUES.get(value, "Unknown")
    raw = text("/sys/firmware/acpi/platform_profile", "Unknown")
    return raw[:1].upper() + raw[1:]


def read_limit():
    value = int_or_none(get_prop("ChargeControlEndThreshold"))
    if value is not None:
        return value
    for path in BATTERY_PATHS:
        value = int_or_none(text(path, ""))
        if value is not None:
            return value
    return None


def nearest_charge_limit(value):
    if value is None:
        return CHARGE_LIMITS[1]
    return min(CHARGE_LIMITS, key=lambda limit: abs(limit - value))


def fan_hwmon():
    for path in glob.glob("/sys/devices/platform/asus-nb-wmi/hwmon/hwmon*"):
        if os.path.exists(os.path.join(path, "fan1_input")):
            return path
    return None


def fan_read(path, filename):
    return int_or_none(text(os.path.join(path, filename), "")) if path else None


def rpm(value):
    return f"{value:,} rpm" if value is not None else "—"
