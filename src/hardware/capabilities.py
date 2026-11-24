"""Capability discovery for optional ASUS and Linux hardware controls."""
import os
import shutil
import glob
import subprocess

from hardware.asus import get_prop


def detect_capabilities():
    """Return conservative feature flags based on exposed interfaces.

    A capability is true only when the corresponding interface or utility is
    visible. The UI can use this result to disable controls instead of
    presenting actions that cannot work on the current machine.
    """
    fan_paths = glob.glob("/sys/class/hwmon/hwmon*")
    fan_paths.extend(glob.glob("/sys/devices/platform/asus-nb-wmi/hwmon/hwmon*"))
    has_fan_sensor = any(os.path.exists(os.path.join(path, "fan1_input")) for path in fan_paths)
    profile = os.path.exists("/sys/firmware/acpi/platform_profile") or get_prop("PlatformProfile") is not None
    charge_limit = get_prop("ChargeControlEndThreshold") is not None or bool(
        glob.glob("/sys/class/power_supply/BAT*/charge_control_end_threshold")
    )
    optional_tools = {
        tool: shutil.which(tool) is not None
        for tool in ("gsettings", "upower", "loginctl", "systemctl", "rfkill", "libinput", "wpctl")
    }
    desktop_touchpad = False
    if optional_tools["gsettings"]:
        try:
            desktop_touchpad = subprocess.run(
                ["gsettings", "list-keys", "org.gnome.desktop.peripherals.touchpad"],
                capture_output=True, text=True, timeout=3,
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    return {
        "performance_profiles": profile,
        "battery_charge_limit": charge_limit,
        "fan_sensors": has_fan_sensor,
        "gpu_switching": any(shutil.which(tool) is not None for tool in ("asusctl", "supergfxctl")),
        "asus_service": shutil.which("asusctl") is not None,
        "nvidia_telemetry": shutil.which("nvidia-smi") is not None,
        "pci_detection": shutil.which("lspci") is not None,
        "desktop_touchpad": desktop_touchpad,
        "optional_tools": optional_tools,
    }
